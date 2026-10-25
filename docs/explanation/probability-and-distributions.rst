Probability and distributions
=============================

Probability describes a repeatable procedure before its result is known. A
distribution turns that description into probabilities for possible values.
Neither is a property bestowed on measurements by collecting enough of them.
Start with :doc:`statistical-foundations` for populations and samples, then use
this chapter to separate a model's predictions from an observed result.

Events, counting, and what is equally likely
-------------------------------------------

A sample space contains the possible outcomes of a procedure. An event is a
subset of those outcomes. For ten coin tosses, an outcome is an ordered string
such as ``HHTHTHHHTH``; the event "exactly eight heads" contains many strings.
If each toss is independent and fair, all :math:`2^{10}=1024` strings have the
same probability. Only under that equal-likelihood assumption can we calculate
an event's probability by dividing favorable outcomes by total outcomes.

There are :math:`\binom{10}{8}=10!/(8!2!)=45` ways to choose the eight head
positions. Therefore, for the head count :math:`K`,

.. math::

   \Pr(K=8)=\frac{45}{1024}=0.0439453125.

"At least eight" is a different event. The disjoint possibilities eight, nine,
and ten heads have counts 45, 10, and 1, giving

.. math::

   \Pr(K\geq8)=\frac{45+10+1}{1024}
   =\frac{56}{1024}=0.0546875.

The point mass is not the upper tail. If a test specified in advance rejects
for unusually *many* heads, its p-value at eight heads is the tail probability,
not the probability of exactly the observed count. A different alternative
requires a different extremeness rule; don't silently reuse this one-sided
calculation for a two-sided question. See :doc:`inference-and-power`.

For performance work, an event might be "a run's p95 exceeds 120 ms." Its
probability depends on a workload and run-generation model, not on counting
the two labels "exceeds" and "doesn't exceed" as equally likely outcomes.

Combining and conditioning events
--------------------------------

For events :math:`A` and :math:`B`, the complement rule is
:math:`\Pr(A^c)=1-\Pr(A)`. To avoid counting their overlap twice,

.. math::

   \Pr(A\cup B)=\Pr(A)+\Pr(B)-\Pr(A\cap B).

Conditional probability restricts attention to outcomes where :math:`B`
occurred:

.. math::

   \Pr(A\mid B)=\frac{\Pr(A\cap B)}{\Pr(B)},\qquad \Pr(B)>0.

Suppose 100 runs include 20 on a busy host. Ten busy-host runs and eight of the
other 80 runs are slow. Then :math:`\Pr(\text{slow})=18/100`, whereas
:math:`\Pr(\text{slow}\mid\text{busy})=10/20=0.5`. These are empirical
proportions from this dataset, not known probabilities for every future host.
They illustrate how environment changes the relevant comparison.

Independence means :math:`\Pr(A\cap B)=\Pr(A)\Pr(B)`. Equivalently, when
conditioning is defined, learning :math:`B` doesn't change the probability of
:math:`A`. Busy and slow aren't independent in the example: their intersection
has probability 0.10, not :math:`0.20(0.18)=0.036`. Independence isn't the same
as disjointness: disjoint events with positive probabilities cannot be
independent because their intersection is empty.

Optional calculation: reversing the condition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bayes' rule follows by writing the intersection two ways:

.. math::

   \Pr(B\mid A)=\frac{\Pr(A\mid B)\Pr(B)}{\Pr(A)}.

In the host example, :math:`\Pr(\text{busy}\mid\text{slow})=10/18`, not
0.5. The overall busy-host frequency matters. Likewise, a small probability
of data under a null hypothesis isn't the probability that the null is true.
Perfcheck doesn't infer that posterior probability from its bootstrap bounds.

Random variables and their moments
---------------------------------

A random variable maps an outcome to a number. The coin string is an outcome;
its head count :math:`K` is a discrete random variable. A run's measured
latency can be modeled as continuous, even though recorded instruments have
finite resolution. Uppercase :math:`X` denotes the random quantity; lowercase
:math:`x` denotes a realized value.

Expectation is a probability-weighted average, not necessarily a possible
individual outcome. Variance measures expected squared distance from it:

.. math::

   \mu=\operatorname{E}[X],\qquad
   \sigma^2=\operatorname{Var}(X)=\operatorname{E}[(X-\mu)^2].

For a fair zero-or-one indicator, :math:`\mu=0.5` and
:math:`\sigma^2=0.25`; no toss realizes 0.5 heads. More generally, an indicator
with success probability :math:`p` has mean :math:`p` and variance
:math:`p(1-p)`. Standard deviation :math:`\sigma` is back in the original
units, while variance has squared units. For a latency model, milliseconds
and square milliseconds aren't interchangeable.

Linearity gives :math:`\operatorname{E}[X+Y]=\operatorname{E}[X]+
\operatorname{E}[Y]` when the expectations exist, even without independence.
Variances add only when the covariance term vanishes. Shared host contention
can make that term positive, which is why treating dependent scrapes as
independent evidence understates uncertainty. The run-level bridge is developed
in :doc:`experimental-design` and :doc:`measurement-and-summaries`.

PMF, PDF, CDF, survival, and quantiles
------------------------------------

A probability mass function (PMF) assigns :math:`\Pr(X=k)` to each possible
discrete value. Its masses sum to one. A probability density function (PDF)
instead assigns a density :math:`f(x)` to a continuous value. Probability is
*area*, not height:

.. math::

   \Pr(a<X\leq b)=\int_a^b f(x)\,dx.

For an absolutely continuous distribution, :math:`\Pr(X=x)=0` at any single
point. This doesn't make recorded measurements impossible: a rounded reading
represents an interval. Densities can exceed one because their units are the
inverse of the measurement unit; only their total area must be one.

Both discrete and continuous variables have a cumulative distribution function
(CDF) :math:`F(x)=\Pr(X\leq x)`. Define survival here as
:math:`S(x)=\Pr(X>x)=1-F(x)`. At a discrete value, :math:`\Pr(X\geq x)`
also includes the mass at :math:`x`; the strict inequality matters in the coin
example. A population quantile for :math:`0<p<1` is

.. math::

   Q(p)=\inf\{x:F(x)\geq p\}.

Thus :math:`Q(0.95)` describes a location in a distribution. It isn't a
p-value. A latency p95 has latency units; a p-value is a dimensionless
null-model tail probability for a chosen test statistic. Neither is the
probability that a performance change is harmless. Finite-sample quantile
interpolation in perfcheck is described in :doc:`measurement-and-summaries`.

Three useful distribution models
--------------------------------

Binomial: count successes in a fixed number of trials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For :math:`K\sim\operatorname{Binomial}(n,p)`,

.. math::

   \Pr(K=k)=\binom{n}{k}p^k(1-p)^{n-k},\quad k=0,\ldots,n,
   \qquad \operatorname{E}[K]=np,\quad
   \operatorname{Var}(K)=np(1-p).

The model assumes independent trials, a fixed trial count, and the same
success probability on every trial. Ten fair tosses have mean five heads and
variance 2.5. Counting ten timeout indicators might look similar, but retries
or a shared outage can violate independence. Perfcheck's cohort bootstrap
doesn't assume that run summaries follow a binomial distribution.

Uniform: equal density over an interval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For :math:`X\sim\operatorname{Uniform}(a,b)`, with :math:`a<b`, density is
:math:`1/(b-a)` inside the interval and zero outside. The CDF is zero below
:math:`a`, :math:`(x-a)/(b-a)` inside, and one above :math:`b`.
Its mean is :math:`(a+b)/2` and variance is :math:`(b-a)^2/12`.

For a modeled delay uniform between zero and two seconds,
:math:`\Pr(0.5<X\leq1)=0.5/2=0.25` and :math:`Q(0.95)=1.9` seconds.
Changing units to milliseconds makes the density 1/2000 per millisecond but
doesn't change any probability. Uniform is a useful model for deliberately
randomized delay; "values stay within bounds" alone doesn't justify it.
Perfcheck doesn't turn a bounded metric into a uniform model.

Normal: a model for symmetric variation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For :math:`X\sim N(\mu,\sigma^2)`, with :math:`\sigma>0`,

.. math::

   f(x)=\frac{1}{\sigma\sqrt{2\pi}}
   \exp\left(-\frac{(x-\mu)^2}{2\sigma^2}\right).

Standardization gives :math:`Z=(X-\mu)/\sigma\sim N(0,1)`; its CDF is
usually written :math:`\Phi`. In a hypothetical normal latency model with
mean 100 ms and SD 10 ms, :math:`\Pr(X\leq110)=\Phi(1)\approx0.8413`
and p95 is approximately :math:`100+1.64485(10)=116.45` ms.
These numbers depend on the model. Real latency is often skewed, mixed, or
heavy-tailed, and a normal model even assigns some probability to negative
values. Perfcheck doesn't require raw observations to be normal.

Averages: LLN and CLT answer different questions
-----------------------------------------------

For IID observations with finite expectation, the law of large numbers (LLN)
says the sample mean converges to that expectation as sample size grows. It
explains why averages can stabilize. It doesn't remove selection bias or say
how close one finite average must be.

For IID observations with finite positive variance, the classical central
limit theorem (CLT) says

.. math::

   \frac{\bar{X}_n-\mu}{\sigma/\sqrt{n}}
   \ \xrightarrow{d}\ N(0,1).

The approximation concerns the *sampling distribution of the mean*, not the
shape of individual measurements. As an illustration, the mean of 100
independent zero-to-two-second uniform delays has expectation one second and
standard error :math:`\sqrt{1/3}/10\approx0.0577` seconds. Its distribution
can be approximately bell-shaped although each input is uniform. Neither 30
nor any other fixed count is a universal normality threshold; skew and tails
affect approximation quality.

Dependence and changing distributions need other results and other assumptions.
Increasing the number of scrapes from one busy host isn't the same experiment
as repeating independent runs. Use :doc:`experimental-design` before applying
this intuition, then continue to :doc:`inference-and-power` and
:doc:`multiple-testing`. To connect these ideas to artifacts, revisit
`lesson 06 <../../examples/06-statistical-foundations.py>`_.
