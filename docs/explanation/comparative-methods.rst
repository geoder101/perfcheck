Comparative methods
===================

The same observations can support different questions, but the answers are not
interchangeable. :download:`Lesson 10 <../../examples/10-comparative-methods.py>`
computes the four contrasts below with fixed local data and no new dependencies.
These are teaching calculations, not verified artifacts or alternate CLI modes.
The implemented rule remains in :doc:`decisions-and-limitations`; lesson 08
demonstrates that rule and :doc:`plain-python-mechanics` exposes its arithmetic.

Welch/t
-------

Dataset: independent toy current runs ``(4, 5, 6)`` and baseline runs
``(1, 2, 3)``, in a common measurement unit.

Question: how separated are the two means in estimated standard-error units?

Assumptions: independent samples, finite nonzero variance, and normal populations
or a suitable approximation for the usual t-tail interpretation. With only three
runs per group, these observations cannot establish that approximation. Welch
uses each group's own variance; a pooled t-test additionally assumes equal
population variances, and paired designs need a different analysis.

Result: means 5 and 2, sample variances 1 and 1 give
:math:`t=3/\sqrt{1/3+1/3}=3.674235` and approximate Welch--Satterthwaite degrees
of freedom 4. Equal sample variances are a fixture convenience, not a pooling
assumption. The lesson reports no Welch p-value: a standardized difference is
not the probability of a regression or a comparison with a practical threshold.
See `NIST's two-sample t reference
<https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm>`_.

Welch/t does not determine perfcheck PASS/FAIL and does not change product policy.

Seeded permutation
------------------

Dataset: the same current ``(4, 5, 6)`` and baseline ``(1, 2, 3)`` values.

Question: under label relabeling, is the current-minus-baseline mean difference
unusually large (the preselected greater tail, including equality)?

Assumptions: exchangeability of labels under the null must follow from the
sampling or randomization design. Serial dependence, paired observations or
systematic workload changes can invalidate independent relabeling. Fixing a seed
does not repair any of those conditions.

Result: observed difference 3, PCG64 seed 42 and 15 random allocations, retaining
three observations per group. This is a deliberately coarse Monte Carlo test,
not an exhaustive one: there are 20 distinct group allocations. Only one exact
allocation reaches difference 3, so the exact greater-tail fraction is 1/20.
The seeded lesson reports its simulated p-value separately, using the standard
plus-one correction and resolution 1/16: one extreme draw gives
``(1+1)/(15+1) = 0.125``. It need not equal 1/20.
Observations are assigned without replacement within an allocation; allocations
can repeat between draws. That differs from a bootstrap's with-replacement
resampling within each cohort. This transparent calculation is confined to the
lesson; no homemade production p-value routine or reusable test API is added.
See `SciPy's permutation_test definition and randomized-test convention
<https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html>`_.
A null-tail probability is not the probability that the null is true; a large
one does not establish equivalence, and a small one does not establish causality.

Permutation does not determine perfcheck PASS/FAIL and does not change product policy.

Mann--Whitney ranks
-------------------

Dataset: current ``(2, 3, 3)``, baseline ``(1, 2, 4)``, with a cross-group tie
at 2 and a within-current tie at 3.

Question: how often does a current observation outrank a baseline observation?

Assumptions: independent samples and meaningful ordering. A location-shift or
median interpretation needs additional common-shape assumptions; Mann--Whitney
is not automatically a median test. Ties require explicit handling.

Result: average pooled ranks in current-then-baseline order are
``(2.5, 4.5, 4.5, 1, 2.5, 6)``. The current rank sum is 11.5 and
:math:`U=11.5-3(4)/2=5.5`. Among nine cross-group pairs there are five current
wins and one tie, so :math:`U/9=0.611111` with half credit for the tie. This is
an observed rank score, not a posterior probability or a practical effect size
in measurement units. Monotone transformations preserve these ranks but can
change mean differences; ranks discard magnitude information. No rank-test
p-value is computed. See `the Mann/Whitney lecture notes
<https://biostat.jhsph.edu/~iruczins/teaching/140.652/lecture26.pdf>`_.

Mann--Whitney does not determine perfcheck PASS/FAIL and does not change product policy.

Bayesian posterior
------------------

Dataset: indicators ``(1, 1, 1, 0)`` for whether four independent runs exceeded
a fixed, predeclared latency cutoff. The cutoff is a teaching measurement
definition, not perfcheck's oriented practical-effect threshold.

Question: conditional on the model and prior, what is the probability theta of
a run exceeding that cutoff?

Assumptions: IID Bernoulli observations, constant theta, one fixed cutoff, and
the chosen uniform Beta(1,1) prior. Changing the prior, cutoff or likelihood
changes the question or result. Binarizing latency discards magnitude.

Result: three exceedances and one non-exceedance update Beta(1,1) to Beta(4,2).
The posterior mean is :math:`4/6=0.666667`. Its density is
:math:`20\theta^3(1-\theta)`, with CDF :math:`5x^4-4x^5`, giving
:math:`\Pr(\theta>0.5)=13/16=0.8125`. This analytic calculation uses no simulation.
For prior sensitivity, Beta(2,2) would instead yield Beta(5,3), mean 0.625.
Neither is the probability that a perfcheck regression exists, a posterior on
the cohort mean difference, or an interpretation of a bootstrap percentile.
See `Stan's Bayesian inference explanation
<https://mc-stan.org/docs/stan-users-guide/bayesian-inference.html>`_.

Bayesian does not determine perfcheck PASS/FAIL and does not change product policy.
