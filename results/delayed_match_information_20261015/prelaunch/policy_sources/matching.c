/* External ABI5 information instrument. Only ctl_api.h is visible in this TU.
 * Exact proposed rule: ../INSTRUMENT_SPEC_DRAFT.md. No hidden-world access. */
#include "ctl_api.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

enum { MATCH_I=10, MATCH_E=11, MATCH_P=12, MATCH_N=13, MATCH_B=14, MH=1024, MS=19 };
typedef struct {
  int role, stage, decision, initialized, stopped, failed;
  double count[MS], L, last_u, qx[MH], qy[MH], logw[MH], w[MH];
} Match;
static const double M_PI2=6.283185307179586476925286766559;

static double sample_rate(double x, double y, double sigma) {
  return 0.05 + 2.0*exp(-(x*x+y*y)/(2.0*sigma*sigma));
}
static double posterior_n(double L) {
  if (L >= 0.0) return 1.0/(1.0+exp(-L));
  const double z=exp(L); return z/(1.0+z);
}
static double gross_score(double pn, double hn, double hb) {
  return (550.0*pn-50.0)*hn + (550.0*(1.0-pn)-50.0)*hb;
}
static double field_rate(const Match *s, int h, double x, double y) {
  const double nx=x-s->qx[h],ny=y-s->qy[h],bx=x+s->qx[h],by=y+s->qy[h];
  return 0.05 + 2.0*exp(-(nx*nx+ny*ny)/(2.0*0.6*0.6))
              + 2.0*exp(-(bx*bx+by*by)/(2.0*1.2*1.2));
}
static void hit_probabilities(const Match *s, double x, double y, double *hn, double *hb) {
  *hn=0.0; *hb=0.0;
  for (int h=0;h<MH;h++) {
    const double nx=x-s->qx[h],ny=y-s->qy[h],bx=x+s->qx[h],by=y+s->qy[h];
    if (nx*nx+ny*ny <= 1.0) *hn += s->w[h];
    if (bx*bx+by*by <= 1.0) *hb += s->w[h];
  }
}
static int normalize(Match *s) {
  double mx=s->logw[0],sum=0.0;
  for (int h=0;h<MH;h++) {
    if (!isfinite(s->logw[h])) return -1;
    if (s->logw[h]>mx) mx=s->logw[h];
  }
  for (int h=0;h<MH;h++) { s->w[h]=exp(s->logw[h]-mx); sum += s->w[h]; }
  if (!(sum>0.0) || !isfinite(sum)) return -1;
  for (int h=0;h<MH;h++) s->w[h]/=sum;
  return 0;
}
static void geometry_init(Ctl *k, Match *s) {
  const CtlInfo *v=ctl_public(k);
  for (int j=0;j<64;j++) for (int r=0;r<16;r++) {
    const int h=j*16+r;
    const double angle=M_PI2*((double)j+0.5)/64.0, radius=2.0+2.0*((double)r+0.5)/16.0;
    s->qx[h]=radius*cos(angle); s->qy[h]=radius*sin(angle);
    s->logw[h]=0.0; s->w[h]=1.0/MH;
  }
  s->last_u=v->t0+65.0; s->initialized=1;
}
static void geometry_to(Ctl *k, Match *s, double u) {
  const CtlInfo *v=ctl_public(k);
  if (!s->initialized) geometry_init(k,s);
  while (s->last_u<u) {
    const double a=s->last_u;
    double b=u;
    double grid=v->t0+65.0+(floor((a-v->t0-65.0)/0.25)+1.0)*0.25;
    if (!(grid>a)) grid=nextafter(a,INFINITY);
    if (grid<b) b=grid;
    const double impulse=ctl_next_impulse_after(k,a);
    if (impulse<b) b=impulse;
    const double mid=a+0.5*(b-a),dt=b-a;
    double x,y; ctl_eff_pos(k,mid,&x,&y);
    for (int h=0;h<MH;h++) {
      double rate=0.0;
      for (int r=0;r<MS;r++) rate += field_rate(s,h,x+v->sense_xy[2*r],y+v->sense_xy[2*r+1]);
      s->logw[h] -= dt*rate;
    }
    s->last_u=b;
  }
}
static int match_init_role(Ctl *k,int role) {
  const CtlInfo *v=ctl_public(k);
  if (v->np!=2 || (v->p[0]!=0.25 && v->p[0]!=0.5) || (v->p[1]!=0.75 && v->p[1]!=0.9) ||
      v->T!=85.0 || v->d_min!=0.5 || v->d0!=1.0 || v->n_sense!=MS || v->n_act!=37 || v->hot<0) return -1;
  Match *s=calloc(1,sizeof *s); if (!s) return -1;
  s->role=role; ctl_set_state(k,s);
  ctl_wake(k,v->t0+14.0); return 0;
}
static void match_ping(Ctl *k,double t,int sensor) {
  Match *s=ctl_state(k); const CtlInfo *v=ctl_public(k);
  const double rel=t-v->t0;
  if (sensor<0 || sensor>=MS || s->failed || s->stopped) return;
  if (rel>=0.5 && rel<14.0 && (s->role==MATCH_I || s->role==MATCH_E)) s->count[sensor]+=1.0;
  if (rel<65.5) return;
  geometry_to(k,s,t-v->d_min);
  double x,y; ctl_eff_pos(k,t-v->d_min,&x,&y);
  x+=v->sense_xy[2*sensor]; y+=v->sense_xy[2*sensor+1];
  for (int h=0;h<MH;h++) s->logw[h]+=log(field_rate(s,h,x,y));
}
static void match_decide(Ctl *k,Match *s,double t) {
  const CtlInfo *v=ctl_public(k);
  geometry_to(k,s,t-v->d_min);
  if (normalize(s)) { s->failed=1; ctl_diagnostic(k,15,1.0); return; }
  int mode=0; for (int h=1;h<MH;h++) if (s->w[h]>s->w[mode]) mode=h;
  const double x[2]={s->qx[mode],-s->qx[mode]},y[2]={s->qy[mode],-s->qy[mode]};
  const double pn=posterior_n(s->L);
  double ex,ey; ctl_eff_final(k,&ex,&ey);
  double hn,hb,score[2],dist[2];
  for (int a=0;a<2;a++) {
    hit_probabilities(s,x[a],y[a],&hn,&hb); score[a]=gross_score(pn,hn,hb);
    dist[a]=(x[a]-ex)*(x[a]-ex)+(y[a]-ey)*(y[a]-ey);
  }
  int selected=0;
  if (score[1]>score[0] || (score[1]==score[0] && (dist[1]<dist[0] ||
      (dist[1]==dist[0] && (x[1]<x[0] || (x[1]==x[0] && y[1]<y[0])))))) selected=1;
  if (s->role==MATCH_N) selected=0;
  if (s->role==MATCH_B) selected=1;
  ctl_steer(k,x[selected]-ex,y[selected]-ey,t,1.0,0.5,0.15);
  const double last=ctl_last_fire(k,v->hot);
  double ta=t+v->d0; if (last+0.5>ta) ta=last+0.5;
  double px,py; ctl_eff_pos(k,ta,&px,&py); hit_probabilities(s,px,py,&hn,&hb);
  const double physical=selected ? hb : hn;
  ctl_diagnostic(k,7,pn); ctl_diagnostic(k,8,selected); ctl_diagnostic(k,9,physical);
  if (physical>=v->p[1] && ta<v->t0+v->T && ctl_tap_would_click(k,1.0,ta)) {
    ctl_fire(k,v->hot,1.0,ta); s->stopped=1;
    ctl_diagnostic(k,10,t-v->t0);
  }
}
static void match_wake(Ctl *k,double t) {
  Match *s=ctl_state(k); const CtlInfo *v=ctl_public(k);
  if (s->failed || s->stopped) return;
  if (s->stage==0) {
    if (s->role==MATCH_I || s->role==MATCH_E) for (int r=0;r<MS;r++) {
      const double x=v->sense_xy[2*r],y=v->sense_xy[2*r+1];
      const double rn=sample_rate(x,y,0.6),rb=sample_rate(x,y,1.2);
      s->L += s->count[r]*log(rn/rb)-13.5*(rn-rb);
    }
    memset(s->count,0,sizeof s->count); ctl_diagnostic(k,5,s->L);
    s->stage=1; ctl_wake(k,v->t0+30.0); return;
  }
  if (s->stage==1) {
    if (s->role!=MATCH_I) s->L=0.0;
    ctl_diagnostic(k,6,s->L); s->stage=2; ctl_wake(k,v->t0+65.5); return;
  }
  match_decide(k,s,t);
  s->decision++;
  if (!s->stopped && !s->failed) ctl_wake(k,v->t0+65.5+(double)s->decision*v->p[0]);
}
static void match_fini(Ctl *k) { free(ctl_state(k)); }
#define MATCH_ROLE(name,id) \
  static int name##_init(Ctl *k) { return match_init_role(k,id); } \
  static const CtlDef name={id,#name,name##_init,match_ping,match_wake,match_fini}; \
  CTL_REGISTER(name)
MATCH_ROLE(retain,MATCH_I)
MATCH_ROLE(erase,MATCH_E)
MATCH_ROLE(post_blank,MATCH_P)
MATCH_ROLE(fixed_narrow,MATCH_N)
MATCH_ROLE(fixed_broad,MATCH_B)
