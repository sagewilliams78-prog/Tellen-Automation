(function(){'use strict';var g,aa=typeof Object.create=="function"?Object.create:function(a){function b(){}
b.prototype=a;return new b},h=typeof Object.defineProperties=="function"?Object.defineProperty:function(a,b,c){if(a==Array.prototype||a==Object.prototype)return a;
a[b]=c.value;return a};
function ba(a){a=["object"==typeof globalThis&&globalThis,a,"object"==typeof window&&window,"object"==typeof self&&self,"object"==typeof global&&global];for(var b=0;b<a.length;++b){var c=a[b];if(c&&c.Math==Math)return c}throw Error("Cannot find global object");}
var ca=ba(this);function k(a,b){if(b)a:{var c=ca;a=a.split(".");for(var d=0;d<a.length-1;d++){var e=a[d];if(!(e in c))break a;c=c[e]}a=a[a.length-1];d=c[a];b=b(d);b!=d&&b!=null&&h(c,a,{configurable:!0,writable:!0,value:b})}}
var l;if(typeof Object.setPrototypeOf=="function")l=Object.setPrototypeOf;else{var m;a:{var da={a:!0},n={};try{n.__proto__=da;m=n.a;break a}catch(a){}m=!1}l=m?function(a,b){a.__proto__=b;if(a.__proto__!==b)throw new TypeError(a+" is not extensible");return a}:null}var p=l;
function q(a){var b=0;return function(){return b<a.length?{done:!1,value:a[b++]}:{done:!0}}}
function r(a){var b=typeof Symbol!="undefined"&&Symbol.iterator&&a[Symbol.iterator];if(b)return b.call(a);if(typeof a.length=="number")return{next:q(a)};throw Error(String(a)+" is not an iterable or ArrayLike");}
k("Symbol",function(a){function b(f){if(this instanceof b)throw new TypeError("Symbol is not a constructor");return new c(d+(f||"")+"_"+e++,f)}
function c(f,v){this.h=f;h(this,"description",{configurable:!0,writable:!0,value:v})}
if(a)return a;c.prototype.toString=function(){return this.h};
var d="jscomp_symbol_"+(Math.random()*1E9>>>0)+"_",e=0;return b});
k("Symbol.iterator",function(a){if(a)return a;a=Symbol("Symbol.iterator");h(Array.prototype,a,{configurable:!0,writable:!0,value:function(){return ha(q(this))}});
return a});
function ha(a){a={next:a};a[Symbol.iterator]=function(){return this};
return a}
k("Symbol.dispose",function(a){return a?a:Symbol("Symbol.dispose")});
function ia(a,b){a instanceof String&&(a+="");var c=0,d=!1,e={next:function(){if(!d&&c<a.length){var f=c++;return{value:b(f,a[f]),done:!1}}d=!0;return{done:!0,value:void 0}}};
e[Symbol.iterator]=function(){return e};
return e}
k("Object.values",function(a){return a?a:function(b){var c=[],d;for(d in b)Object.prototype.hasOwnProperty.call(b,d)&&c.push(b[d]);return c}});
k("Array.prototype.values",function(a){return a?a:function(){return ia(this,function(b,c){return c})}});/*

 Copyright The Closure Library Authors.
 SPDX-License-Identifier: Apache-2.0
*/
var t=this||self;function u(a){a=a.split(".");for(var b=t,c=0;c<a.length;c++)if(b=b[a[c]],b==null)return null;return b}
function w(a,b){a=a.split(".");for(var c=t,d;a.length&&(d=a.shift());)a.length||b===void 0?c[d]&&c[d]!==Object.prototype[d]?c=c[d]:c=c[d]={}:c[d]=b}
;var x=Math.max,ja=x.apply,y=Object.values({ea:1,da:2,ca:4,ia:8,ka:16,ga:32,X:64,aa:128,Y:256,ja:512,Z:1024,ba:2048,ha:4096,fa:8192}),z;if(y instanceof Array)z=y;else{for(var ka=r(y),A,B=[];!(A=ka.next()).done;)B.push(A.value);z=B}ja.call(x,Math,z);function C(){this.B=this.B;this.D=this.D}
C.prototype.B=!1;C.prototype.dispose=function(){this.B||(this.B=!0,this.I())};
C.prototype[Symbol.dispose]=function(){this.dispose()};
C.prototype.I=function(){if(this.D)for(;this.D.length;)this.D.shift()()};var D=t.window,E,F,G=(D==null?void 0:(E=D.yt)==null?void 0:E.config_)||(D==null?void 0:(F=D.ytcfg)==null?void 0:F.data_)||{};w("yt.config_",G);function H(a){a=I(a);return typeof a==="string"&&a==="false"?!1:!!a}
function I(a,b){var c={};a=("EXPERIMENT_FLAGS"in G?G.EXPERIMENT_FLAGS:c)[a];return a!==void 0?a:b}
;var J=1E3/60,la=Number(I("web_emulated_idle_callback_delay",300)||0),K=J-3,L=[8,5,4,3,2,1,0];function M(a){a=a===void 0?{}:a;C.call(this);var b=this;this.j=[];this.i={};this.G=this.h=0;this.F=this.m=!1;this.A=[];this.C=this.H=!1;for(var c=r(L),d=c.next();!d.done;d=c.next())this.j[d.value]=[];this.l=0;this.S=a.timeout||1;this.v=K;this.o=0;this.J=this.V.bind(this);this.R=this.W.bind(this);this.M=this.T.bind(this);this.N=this.U.bind(this);this.O=this.L.bind(this);this.P=function(){b.L(performance.now())};
this.K=!!window.requestIdleCallback&&!!window.cancelIdleCallback&&!H("disable_scheduler_requestIdleCallback");((this.u=a.useRaf!==!1&&!!window.requestAnimationFrame)||H("enable_scheduler_simulate_raf"))&&document.addEventListener("visibilitychange",this.J)}
M.prototype=aa(C.prototype);M.prototype.constructor=M;if(p)p(M,C);else for(var N in C)if(N!="prototype")if(Object.defineProperties){var O=Object.getOwnPropertyDescriptor(C,N);O&&Object.defineProperty(M,N,O)}else M[N]=C[N];function P(a,b){var c=Date.now();Q(b);b=Date.now()-c;a.m||(a.v-=b)}
function R(a,b,c,d){++a.G;if(c===10)return P(a,b),a.G;var e=a.G;a.i[e]=b;a.m&&!d?a.A.push({id:e,priority:c}):(a.j[c].push(e),a.F||a.m||(a.h!==0&&S(a)!==a.o&&T(a),a.start()));return e}
function U(a){a.A.length=0;for(var b=5;b>=0;b--)a.j[b].length=0;a.j[8].length=0;a.i={};T(a)}
function S(a){var b=H("enable_scheduler_simulate_raf");if(a.j[8].length){if(a.C)return 4;if(b){if(!document.hidden)return a.u?3:5}else if(!document.hidden&&a.u)return 3}for(var c=5;c>=a.l;c--)if(a.j[c].length>0)return c>0?b?document.hidden?2:a.u?3:5:!document.hidden&&a.u?3:2:1;return 0}
function ma(a){var b=u("yt.logging.errors.log");b&&b(a)}
function Q(a){try{a()}catch(b){ma(b)}}
function na(a){for(var b=r(L),c=b.next();!c.done;c=b.next())if(a.j[c.value].length)return!0;return!1}
g=M.prototype;g.U=function(a){var b=void 0;a&&(b=a.timeRemaining());this.H=!0;V(this,b);this.H=!1};
g.W=function(){V(this)};
g.T=function(){oa(this)};
g.L=function(a){this.C=!0;var b=S(this);b===4&&b!==this.o&&(T(this),this.start());V(this,void 0,a);this.C=!1};
g.V=function(){document.hidden||oa(this);this.h&&(T(this),this.start())};
function oa(a){T(a);a.m=!0;for(var b=Date.now(),c=a.j[8];c.length;){var d=c.shift(),e=a.i[d];delete a.i[d];e&&Q(e)}pa(a);a.m=!1;na(a)&&a.start();a.v-=Date.now()-b}
function pa(a){for(var b=0,c=a.A.length;b<c;b++){var d=a.A[b];a.j[d.priority].push(d.id)}a.A.length=0}
function V(a,b,c){a.C&&a.o===4&&a.h||T(a);a.m=!0;b=Date.now()+(b||a.v);for(var d=a.j[5];d.length;){var e=d.shift(),f=a.i[e];delete a.i[e];if(f)try{f(c)}catch(va){ma(va)}}for(d=a.j[4];d.length;)c=d.shift(),e=a.i[c],delete a.i[c],e&&Q(e);d=a.H?0:1;d=a.l>d?a.l:d;if(!(Date.now()>=b)){do{a:{c=a;e=d;for(f=3;f>=e;f--)for(var v=c.j[f];v.length;){var ea=v.shift(),fa=c.i[ea];delete c.i[ea];if(fa){c=fa;break a}}c=null}c&&Q(c)}while(c&&Date.now()<b)}a.m=!1;pa(a);a.v=K;na(a)&&a.start()}
g.start=function(){this.F=!1;if(this.h===0)switch(this.o=S(this),this.o){case 1:var a=this.N;this.h=this.K?window.requestIdleCallback(a,{timeout:3E3}):window.setTimeout(a,la);break;case 2:this.h=window.setTimeout(this.R,this.S);break;case 3:this.h=window.requestAnimationFrame(this.O);break;case 4:this.h=window.setTimeout(this.M,0);break;case 5:this.h=window.setTimeout(this.P,J)}};
function T(a){if(a.h){switch(a.o){case 1:var b=a.h;a.K?window.cancelIdleCallback(b):window.clearTimeout(b);break;case 5:case 2:case 4:window.clearTimeout(a.h);break;case 3:window.cancelAnimationFrame(a.h)}a.h=0}}
g.I=function(){U(this);T(this);(this.u||H("enable_scheduler_simulate_raf"))&&document.removeEventListener("visibilitychange",this.J);C.prototype.I.call(this)};var W=u("yt.scheduler.instance.timerIdMap_")||{},qa=Number(I("kevlar_tuner_scheduler_soft_state_timer_ms",800)||0),X=0,Y=0;function Z(){var a=u("ytglobal.schedulerInstanceInstance_");if(!a||a.B)a=new M(("scheduler"in G?G.scheduler:void 0)||{}),w("ytglobal.schedulerInstanceInstance_",a);return a}
function ra(){sa();var a=u("ytglobal.schedulerInstanceInstance_");a&&(a&&typeof a.dispose=="function"&&a.dispose(),w("ytglobal.schedulerInstanceInstance_",null))}
function sa(){U(Z());for(var a in W)W.hasOwnProperty(a)&&delete W[Number(a)]}
function ta(a,b,c){if(!c)return c=c===void 0,-R(Z(),a,b,c);var d=window.setTimeout(function(){var e=R(Z(),a,b);W[d]=e},c);
return d}
function ua(a){var b=Z();P(b,a)}
function wa(a){var b=Z();if(a<0)delete b.i[-a];else{var c=W[a];c?(delete b.i[c],delete W[a]):window.clearTimeout(a)}}
function xa(){ya()}
function ya(){window.clearTimeout(X);Z().start()}
function za(){var a=Z();T(a);a.F=!0;window.clearTimeout(X);X=window.setTimeout(xa,qa)}
function Aa(){window.clearTimeout(Y);Y=window.setTimeout(function(){Ba(0)},qa)}
function Ba(a){Aa();var b=Z();b.l=a;b.start()}
function Ca(a){Aa();var b=Z();b.l>a&&(b.l=a,b.start())}
function Da(){window.clearTimeout(Y);var a=Z();a.l=0;a.start()}
;u("yt.scheduler.initialized")||(w("yt.scheduler.instance.dispose",ra),w("yt.scheduler.instance.addJob",ta),w("yt.scheduler.instance.addImmediateJob",ua),w("yt.scheduler.instance.cancelJob",wa),w("yt.scheduler.instance.cancelAllJobs",sa),w("yt.scheduler.instance.start",ya),w("yt.scheduler.instance.pause",za),w("yt.scheduler.instance.setPriorityThreshold",Ba),w("yt.scheduler.instance.enablePriorityThreshold",Ca),w("yt.scheduler.instance.clearPriorityThreshold",Da),w("yt.scheduler.initialized",!0));}).call(this);
