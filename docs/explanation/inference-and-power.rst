Inference and power
===================

Read :doc:`probability-and-distributions` for random variables, CDFs and sampling
distributions, and :doc:`experimental-design` for the distinction between a run
and an independent experimental unit. Here we turn those ideas into a complete
inferential argument. The calculations are teaching models, not additional
perfcheck commands. The product's actual decision is in
:doc:`uncertainty-and-comparison` and :doc:`decisions-and-limitations`.

From a question to a decision
----------------------------

A test needs more than a formula for a statistic. It needs a question, a null
model, a direction of departure, and a rule chosen before inspecting the result.
Consider a coin tossed independently ten times:

1. **Question:** is the probability of heads greater than one half?
2. **Hypotheses:** :math:`H_0:\theta\leq 1/2` against
   :math:`H_1:\theta>1/2`. The boundary :math:`\theta=1/2` gives the largest
   upper-tail rejection probability within this null.
3. **Statistic:** :math:`K`, the number of heads. Suppose we observe eight.
4. **Null distribution:** at the boundary,
   :math:`K\sim\operatorname{Binomial}(10,1/2)`.
5. **Tail:** large counts support the preselected alternative, so include every
   count at least as large as eight, including equality.
6. **p-value:**

   .. math::

      p=\Pr_{1/2}(K\geq8)
       =\frac{\binom{10}{8}+\binom{10}{9}+\binom{10}{10}}{2^{10}}
       =\frac{45+10+1}{1024}=0.0546875.

7. **Criterion:** with a predeclared :math:`\alpha=0.05`, reject when
   :math:`p\leq\alpha`. Here we don't reject.

The probability of exactly eight heads is :math:`45/1024=0.0439453125`.
That mass is not the p-value. It omits outcomes even more favorable to the
alternative. Substituting it would reverse this decision incorrectly.
For this symmetric boundary model, a two-sided test based on distance from five
would include :math:`K\leq2` as well as :math:`K\geq8`, giving :math:`112/1024`.
Other discrete two-sided conventions need an explicit definition. Don't choose
one or two sides after seeing which produces the smaller answer.

A p-value is a null-tail probability for this procedure. It isn't
:math:`\Pr(H_0\mid\text{data})`, the probability of a chance explanation, or the
size of an effect. Not rejecting leaves the null unresolved; it doesn't prove
fairness. The discreteness also means that a nominal 5% rule need not reject
exactly 5% of fair-coin experiments.

A continuous flagship: a known-sigma mean
----------------------------------------

Now ask whether a population mean has fallen below 100 measurement units.
Suppose :math:`X_1,\ldots,X_{25}` are independent normal observations with
unknown mean :math:`\mu` and genuinely known population SD :math:`\sigma=10`.
This strong assumption makes an exact calculation possible:

* Question: is the mean smaller than 100?
* Hypotheses: :math:`H_0:\mu\geq100`, :math:`H_1:\mu<100`.
* Statistic: :math:`Z=(\overline X-100)/(10/\sqrt{25})`.
* Null distribution: at :math:`\mu=100`, :math:`Z\sim N(0,1)`.
* Tail: small values of :math:`Z` favor the alternative.
* Observed result: :math:`\overline x=96` gives :math:`\mathrm{SE}=2`,
  :math:`z=-2`, and :math:`p=\Phi(-2)=0.02275013` approximately.
* Criterion: reject at the predeclared one-sided level 0.05, since
  :math:`-2<\Phi^{-1}(0.05)=-1.644854`.

Under larger null means, this lower-tail event is even less likely. If 10 were
an estimated sample SD instead, the exact normal pivot would no longer follow
from these assumptions. An estimated denominator calls for a different model,
such as a one-sample t procedure for independent normal observations. A large
number of correlated scrapes isn't a substitute for 25 independent runs.

Why valid continuous p-values are uniform
----------------------------------------

Let :math:`T` have continuous null CDF :math:`F_0`. For a lower-tail test,
the p-value is :math:`P=F_0(T)`. Imagine marking a threshold at the null's
20th percentile. Exactly 20% of null draws fall below that threshold, so exactly
20% have a lower-tail p-value at most 0.2. The probability integral transform
makes that reasoning general. When :math:`F_0` is strictly increasing, for
:math:`0<u<1`:

.. math::

   \Pr_0(F_0(T)\leq u)
   =\Pr_0(T\leq F_0^{-1}(u))
   =F_0(F_0^{-1}(u))=u.

Continuity alone suffices with generalized quantiles: flat parts of a continuous
CDF carry no probability, so they don't change the result. Thus
:math:`P\sim\operatorname{Uniform}(0,1)` under the fully specified continuous
null. For upper tails use :math:`1-F_0(T)`; a two-sided transformation must
likewise match the chosen extremeness rule. With a composite null, exact
uniformity may hold only at a boundary, while other null parameter values give
conservative p-values.

For a discrete statistic, attainable tail probabilities have jumps. A valid
nonrandomized p-value instead satisfies the super-uniform property

.. math::

   \Pr_0(P\leq u)\leq u,\qquad 0\leq u\leq1.

In the coin example, :math:`p\leq0.05` requires at least nine heads. Its actual
null rejection probability is :math:`11/1024=0.0107421875`. That conservatism
is not invalidity. In contrast, using only the point mass, dropping ties from
a discrete tail, ignoring data-dependent selection, or using the wrong null
distribution can violate the inequality. A number between zero and one isn't
automatically a calibrated p-value. Mid-p conventions, which allocate half the
observed mass, can be useful approximations but aren't generally super-uniform.

Confidence intervals describe a procedure
----------------------------------------

For the normal model with known sigma, the pivot gives

.. math::

   \Pr_\mu\left(-1.96\leq
      \frac{\overline X-\mu}{\sigma/\sqrt n}\leq1.96\right)
   \approx0.95.

Rearranging the inequalities produces the random interval
:math:`[\overline X-1.96\sigma/\sqrt n,
\overline X+1.96\sigma/\sqrt n]`. Across repeated datasets under that model,
approximately 95% of these intervals contain the fixed true mean. For the
observed mean 96, it is :math:`[92.08,99.92]`. Once observed, this frequentist
interval either covers the fixed mean or doesn't; the 95% refers to the
construction, not a posterior probability assigned to this particular interval.

Tests and intervals are dual when they invert the **same** family of tests,
with matching assumptions, tails, significance levels and endpoint conventions.
A two-sided level-0.05 normal test rejects precisely those null means excluded
by the corresponding 95% interval, apart from matching boundary conventions.
The lower-tail level-0.05 test above instead corresponds to a 95% **upper**
one-sided confidence bound, :math:`96+1.644854(2)=99.289708`.
For a higher-is-worse regression claim :math:`\Delta>T`, the matching direction
would use a lower one-sided bound above :math:`T`.

Approximate bootstrap bounds don't automatically inherit exact coverage or
test-size guarantees from this algebra. Nor does an interval containing zero
prove equivalence. Equivalence needs a predeclared acceptable margin and a
procedure designed to exclude effects outside it.

Deriving power, rather than reading it from a p-value
----------------------------------------------------

Type I error is rejection under a true null, bounded by :math:`\alpha` for a
valid level-:math:`\alpha` test. Type II error :math:`\beta(\mu_1)` is failure
to reject at a specified alternative :math:`\mu_1`. Power is
:math:`1-\beta(\mu_1)`. There isn't one power number independent of effect size.

For the lower-tail known-sigma test, write :math:`\mu_1=\mu_0-\delta`,
where :math:`\delta>0` is a real decrease, and let
:math:`c=\Phi^{-1}(\alpha)`. The rejection event is
:math:`\overline X<\mu_0+c\sigma/\sqrt n`. Under the alternative,
:math:`(\overline X-\mu_1)/(\sigma/\sqrt n)\sim N(0,1)`, so

.. math::

   \operatorname{Power}(\delta)
    &=\Pr_{\mu_1}(\overline X<\mu_0+c\sigma/\sqrt n)\\
    &=\Phi\left(c+\frac{\delta\sqrt n}{\sigma}\right),\\
   \beta(\delta)&=1-\Phi\left(c+\frac{\delta\sqrt n}{\sigma}\right).

At :math:`\alpha=0.05`, :math:`\sigma=10`, :math:`n=25`, a true decrease of
four units gives power :math:`\Phi(-1.644854+2)\approx0.638760`.
The observed mean 96 gave a small p-value, but the design's power for a true
mean 96 is only about 64%. Those are different probabilities over different
questions. Plugging an observed effect into a post-hoc power calculation doesn't
add independent evidence about whether the null is true.

Solving for target power :math:`1-\beta` gives a planning formula:

.. math::

   n\geq\left(\frac{\sigma}{\delta}\right)^2
          (z_{1-\alpha}+z_{1-\beta})^2,
   \qquad z_q=\Phi^{-1}(q).

For 80% power to detect a four-unit decrease, round
:math:`(10/4)^2(1.644854+0.841621)^2\approx38.640983` up to 39 independent
observations. Halving the effect requires four times the sample size in this
model. Lower alpha requires more observations. For two independent groups,
the SE involves both sample sizes and variances, so this one-sample formula
cannot be copied unchanged. A practical threshold also changes the target:
detecting :math:`\Delta>T` depends on the excess :math:`\Delta-T`, not just the
distance from zero. Real workload planning must revisit variance, dependence,
missingness and costs in :doc:`experimental-design`.

Next steps
----------

Read :doc:`multiple-testing` before inspecting many metrics, then
:doc:`comparative-methods` to see how a different model changes the answer.
:download:`Lab 10 <../../examples/10-comparative-methods.py>` keeps its Welch,
permutation, rank and Bayesian calculations separate from product verdicts.
:download:`Lab 08 <../../examples/08-bootstrap-and-decisions.py>` demonstrates
the implemented bootstrap path, which doesn't compute the p-values above.
