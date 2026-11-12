Comparative methods
===================

The same observations can support different questions, but the answers are not
interchangeable. `Lesson 10 <https://github.com/geoder101/perfcheck/blob/main/examples/10-comparative-methods.py>`_
computes the four contrasts below with fixed local data and no new dependencies.
These are teaching calculations, not verified artifacts or alternate CLI modes.
The implemented rule remains in :doc:`decisions-and-limitations`; lesson 08
demonstrates that rule and :doc:`plain-python-mechanics` exposes its arithmetic.

Prerequisites are :doc:`probability-and-distributions`,
:doc:`experimental-design` and :doc:`inference-and-power`. Keep three questions
separate: what quantity is estimated, what repeated-data model justifies its
uncertainty, and what action follows? A mean difference, rank score and
exceedance probability need not agree because they estimate different things.

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

To see why the denominator has this form, independence gives
:math:`\operatorname{Var}(\overline X_c-\overline X_b)=
\sigma_c^2/n_c+\sigma_b^2/n_b`. Replace the unknown variances with sample
variances, each computed with denominator :math:`n_g-1`. For a null difference
:math:`\Delta_0`, Welch uses

.. math::

   t=\frac{\overline x_c-\overline x_b-\Delta_0}
           {\sqrt{s_c^2/n_c+s_b^2/n_b}},\qquad
   \nu=\frac{(s_c^2/n_c+s_b^2/n_b)^2}
        {(s_c^2/n_c)^2/(n_c-1)+(s_b^2/n_b)^2/(n_b-1)}.

The degrees-of-freedom approximation accounts for the estimated denominator.
Even with independent normal populations and unequal variances, the usual
Welch t reference is generally an approximation, not an exact pivot. In this
equal-size, equal-sample-variance example it gives :math:`\nu=4`.
For a preselected higher-mean alternative the model-based tail would be
:math:`\Pr(t_\nu\geq t_{\mathrm{observed}})`; a two-sided alternative uses
both tails. This describes the inference, not a calculation added to the lab
or product. Setting :math:`\Delta_0=T` can address a practical margin in a
separately designed test; the default zero-difference question doesn't do so.

Unequal variances are allowed, but independence isn't optional. A paired design
instead analyzes within-pair differences and their variance, retaining the
covariance that an independent-samples denominator omits. Severe skew, rare
outliers or small samples can also make the t approximation poor. "Welch"
doesn't mean assumption-free, and a nonsignificant result isn't equivalence.
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

The exact calculation enumerates all :math:`\binom63=20` equally weighted
allocations of three indexed observations to current. For observed statistic
:math:`d_{\mathrm{obs}}=3`,

.. math::

   p_{\mathrm{exact}}=
      \frac{\#\{a:d(a)\geq d_{\mathrm{obs}}\}}{20}=\frac1{20}.

The observed allocation is already among those 20: don't add an extra one to
an exhaustive numerator and denominator. In contrast, the randomized procedure
draws :math:`B` allocations under the null and computes
:math:`p_{\mathrm{MC}}=(b+1)/(B+1)`, where :math:`b` simulated statistics are
at least as extreme as the observed one. The extra one treats the observed
statistic alongside the simulated statistics; under the appropriate null
exchangeability and sampling scheme it avoids reporting an impossible zero
and yields a valid, possibly conservative randomized-test p-value. Its minimum
is :math:`1/(B+1)`. This guarantee isn't permission to apply the formula to
arbitrary simulations or to stop sampling whenever the answer looks favorable.

Unrestricted relabeling assumes the joint null distribution is invariant to
the allowed label changes. Equality of means alone doesn't imply this when
group variances or distribution shapes differ. Randomized assignments can
justify a randomization distribution under a sharp no-effect null; paired or
blocked assignments require the corresponding restricted permutations. A
studentized permutation method can target other nulls under additional
asymptotic assumptions, but isn't what this tiny mean-difference example does.

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

More precisely, **strictly increasing** transformations preserve these ranks
and ties; decreasing transformations reverse their direction. The population
target corresponding to the pair score is
:math:`\Pr(X_c>X_b)+\tfrac12\Pr(X_c=X_b)` for independent draws from the two
populations. Standard rank-test null calibration commonly uses identical
distributions, which is stronger than merely setting this score to one half.
Different shapes can have equal medians but different rank behavior, and a
score of one half doesn't imply identical distributions. To interpret a rank
test as a location or median comparison, impose a justified common-shape
location-shift model. Distribution-free null calibration isn't freedom from
design assumptions; ties also change the reference distribution.

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

The update follows directly from Bayes' rule. Ignoring a factor independent
of :math:`\theta`, the likelihood of three successes and one failure is
:math:`L(\theta)\propto\theta^3(1-\theta)`. A Beta prior has density
:math:`\pi(\theta)\propto\theta^{a-1}(1-\theta)^{b-1}` on :math:`(0,1)`.
Multiplication gives

.. math::

   \pi(\theta\mid x)
      =\frac{L(\theta)\pi(\theta)}
             {\int_0^1L(v)\pi(v)\,dv}
      \propto\theta^{a+3-1}(1-\theta)^{b+1-1}.

Thus the posterior is Beta(:math:`a+3,b+1`). With the uniform prior the
normalizing integral is :math:`\int_0^1\theta^3(1-\theta)d\theta=1/20`.
Integrating the normalized density from one half to one gives 0.8125. The
likelihood isn't itself a probability distribution over the parameter; the
prior and normalization are essential to that interpretation.

A posterior credible interval can assign probability to parameter values
conditional on the model and data. A frequentist confidence interval instead
has a repeated-sampling coverage interpretation. Numerical agreement in some
models doesn't make them interchangeable. Neither interpretation validates a
wrong likelihood, a changing workload or a conveniently chosen cutoff. Turning
a posterior into an action additionally needs a decision rule, often a loss
function balancing false alarms and missed problems. The lab doesn't supply a
Bayesian release gate.
See `Stan's Bayesian inference explanation
<https://mc-stan.org/docs/stan-users-guide/how-stan-works.html>`_.

Bayesian does not determine perfcheck PASS/FAIL and does not change product policy.

Choosing the question before the method
--------------------------------------------

The Welch example measures a difference in means, permutation supplies a null
distribution justified by label invariance, ranks measure ordering rather than
units, and the Bayesian example estimates a cutoff-exceedance probability.
None can be substituted silently for another. The classical normal variance
ratio :math:`F=s_c^2/s_b^2` is yet another question: under independent normal
samples with equal population variances it has an F reference distribution
with :math:`n_c-1,n_b-1` degrees of freedom. It tests variances, not mean
regression, and is sensitive to nonnormality. A p-value is a tail summary
used by many tests, not a fifth competing distributional model.

Trying all these approaches and reporting whichever is most persuasive adds
selection to the experiment. Read :doc:`multiple-testing` before doing so.
Then return to `Lab 08 <https://github.com/geoder101/perfcheck/blob/main/examples/08-bootstrap-and-decisions.py>`_
and :doc:`uncertainty-and-comparison` for the actual percentile-bootstrap rule;
its reproducibility isn't evidence that any of the alternative assumptions hold.
