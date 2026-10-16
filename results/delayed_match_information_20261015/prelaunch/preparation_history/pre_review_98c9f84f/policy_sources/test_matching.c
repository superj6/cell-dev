/* Pure supplied-input/math checks: no simulator life or environment random draw. */
#include <assert.h>
#include <stdio.h>
#include "matching.c"

struct Ctl {
  CtlInfo v; void *state; double now, x,y,last[37],diag[16];
  double wakes[256],trace[4096]; int nw,nt;
  /* Deliberately inaccessible to matching.c through the opaque public interface. */
  double hidden_class,hidden_phase,hidden_deadline,hidden_target; unsigned long hidden_seed;
};
static const CtlDef *defs[32];
void ctl_register(const CtlDef *d) { assert(d->id<32); defs[d->id]=d; }
const CtlInfo *ctl_public(const Ctl *k) { return &k->v; }
void *ctl_state(const Ctl *k) { return k->state; }
void ctl_set_state(Ctl *k,void *p) { k->state=p; }
void ctl_diagnostic(Ctl *k,int i,double x) { assert(i>=5&&i<16); k->diag[i]=x; }
double ctl_now(const Ctl *k) { return k->now; }
double ctl_wake(Ctl *k,double t) {
  if (t>=k->v.t0+k->v.T) return -1.0;
  if (!(t>k->now)) t=nextafter(k->now,INFINITY);
  assert(k->nw<256); k->wakes[k->nw++]=t; return t;
}
double ctl_fire(Ctl *k,int a,double kap,double t) {
  if (t<k->now+k->v.latency) t=k->now+k->v.latency;
  if (t<k->last[a]+0.5) t=k->last[a]+0.5;
  if (t>=k->v.t0+k->v.T) return -1.0;
  assert(k->nt+4<4096); k->trace[k->nt++]=1.0;k->trace[k->nt++]=t;
  k->trace[k->nt++]=(double)a;k->trace[k->nt++]=kap;k->last[a]=t;return t;
}
double ctl_last_fire(const Ctl *k,int a) { return k->last[a]; }
int ctl_tap_would_click(const Ctl *k,double kap,double t) { (void)k;(void)kap;(void)t;return 1; }
double ctl_next_impulse_after(const Ctl *k,double t) { (void)k;(void)t;return INFINITY; }
void ctl_eff_pos(Ctl *k,double t,double *x,double *y) { (void)t;*x=k->x;*y=k->y; }
void ctl_eff_final(Ctl *k,double *x,double *y) { *x=k->x;*y=k->y; }
int ctl_steer(Ctl *k,double x,double y,double t,double a,double b,double c) {
  (void)a;(void)b;(void)c; assert(k->nt+4<4096);
  k->trace[k->nt++]=2.;k->trace[k->nt++]=t;k->trace[k->nt++]=x;k->trace[k->nt++]=y;return 0;
}
static double xy[38],params[2]={0.5,0.75};
static void setup(Ctl *k,int hidden) {
  memset(k,0,sizeof *k);
  k->v.n_sense=19;k->v.n_act=37;k->v.hot=18;k->v.T=85.;k->v.d_min=.5;k->v.d0=1.;k->v.latency=1.;
  k->v.sense_xy=xy;k->v.p=params;k->v.np=2;k->v.t_ref_min=.5;
  for (int i=0;i<37;i++) k->last[i]=-INFINITY;
  k->hidden_class=hidden;k->hidden_phase=7-hidden;k->hidden_deadline=9+hidden;
  k->hidden_target=100*hidden;k->hidden_seed=42000000UL+hidden;
}
static void supplied(Ctl *k,int role,int hidden) {
  setup(k,hidden);assert(!defs[role]->init(k));
  for (int t=1;t<=12;t++) for (int r=0;r<19;r++) if ((t+r)%4==0) {
    k->now=(double)t;defs[role]->ping(k,k->now,r);
  }
  for (int j=0;j<k->nw;j++) {
    k->now=k->wakes[j];
    if (k->now>=65.5) defs[role]->ping(k,k->now,(j*7)%19);
    defs[role]->wake(k,k->now);
    assert(k->diag[15]==0.0);
  }
  for (int i=0;i<k->nt;i+=4) assert(k->trace[i+1]>=65.5);
}
int main(void) {
  for (int r=1;r<19;r++) { xy[2*r]=3.*cos(M_PI2*(r-1)/18.);xy[2*r+1]=3.*sin(M_PI2*(r-1)/18.); }
  assert(sample_rate(0.,0.,.6)==sample_rate(0.,0.,1.2));
  assert(posterior_n(0.)==.5);assert(posterior_n(100.)>.999);assert(posterior_n(-100.)<.001);
  assert(fabs(gross_score(.9,.2,.7)-92.5)<1e-12);
  Ctl e,p,changed; supplied(&e,MATCH_E,0);supplied(&p,MATCH_P,0);supplied(&changed,MATCH_E,1);
  assert(e.nt==p.nt && e.nt==changed.nt && e.nt>0);
  assert(!memcmp(e.trace,p.trace,(size_t)e.nt*sizeof(double)));
  assert(!memcmp(e.trace,changed.trace,(size_t)e.nt*sizeof(double)));
  Match *se=e.state,*sp=p.state;
  assert(se->L==0.0 && sp->L==0.0);
  assert(!memcmp(se->count,sp->count,sizeof se->count));
  assert(!memcmp(se->logw,sp->logw,sizeof se->logw));
  double sum=0.;for(int h=0;h<MH;h++)sum+=se->w[h];assert(fabs(sum-1.)<1e-12);
  defs[MATCH_E]->fini(&e);defs[MATCH_P]->fini(&p);defs[MATCH_E]->fini(&changed);
  /* A perfectly localized physical target permits a neutral-memory tap. */
  Ctl neutral;setup(&neutral,0);assert(!defs[MATCH_E]->init(&neutral));
  Match *s=neutral.state;geometry_init(&neutral,s);s->stage=2;s->last_u=65.;s->L=0.;
  for(int h=0;h<MH;h++)s->logw[h]=-1000.;s->logw[0]=0.;
  neutral.x=-s->qx[0];neutral.y=-s->qy[0];neutral.now=65.5;
  match_decide(&neutral,s,65.5);assert(s->stopped && neutral.diag[9]>.999);
  assert(neutral.diag[7]==.5);assert(neutral.nt==8); /* steering plus ordinary hotspot spike */
  assert(neutral.trace[2]!=0. || neutral.trace[3]!=0. || neutral.x!=0.); /* real goal, not origin */
  defs[MATCH_E]->fini(&neutral);
  puts("PASS supplied-input hidden-state replay, E/P identity, physical neutral tap, both-width gross, normalization, center null");
  return 0;
}
