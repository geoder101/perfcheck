Glossary
========

These definitions distinguish general statistical ideas from perfcheck's
recorded evidence. For worked examples, see
:doc:`../explanation/probability-and-distributions`,
:doc:`../explanation/experimental-design`,
:doc:`../explanation/inference-and-power`, and
:doc:`../explanation/multiple-testing`.

.. glossary::
   :sorted:

   alpha
      A test's chosen Type I error level under its null model and assumptions.
      It isn't the probability that a particular conclusion is wrong.
      Perfcheck records nominal and multiplicity-adjusted effective alpha for
      its policy rule without guaranteeing exact bootstrap error rates.

   alternative hypothesis
      The parameter values or distributions against which a null hypothesis
      is assessed. Directional and two-sided alternatives define different
      notions of an extreme result.

   Bayes' rule
      The identity :math:`\Pr(B\mid A)=\Pr(A\mid B)\Pr(B)/\Pr(A)` for
      :math:`\Pr(A)>0`. Reversing a condition requires the base probabilities.

   Bessel correction
      Division of the sum of squared deviations from the sample mean by
      :math:`n-1` rather than :math:`n`. Under IID finite-variance sampling,
      this makes sample variance, but not its square root, unbiased.

   Benjamini--Hochberg procedure
      A step-up multiple-testing procedure that compares ordered p-values
      with rank-scaled thresholds to control FDR under specified validity
      and dependence assumptions. It isn't perfcheck's Bonferroni policy.

   beta
      The Type II error probability for a specified alternative and test
      procedure. Power at that alternative is :math:`1-\beta`.

   between-run variation
      Variation in a chosen per-run summary across runs. It isn't measured
      by the standard deviation of scrapes within a single run.

   bias
      For an estimator, the difference between its expectation and the target
      parameter. Selection and measurement mechanisms can introduce bias
      that collecting more observations doesn't remove.

   binomial distribution
      The distribution of the number of successes in a fixed number of
      independent trials with a common success probability.

   blocking
      Grouping similar experimental conditions so treatments can be compared
      within those groups. A blocked design may need an analysis that
      accounts for the groups; it isn't automatically a paired analysis.

   Bonferroni adjustment
      Allocation of alpha across a family of :math:`m` tests, commonly as
      :math:`\alpha/m` per test. The union bound gives family-wise error
      control if each test meets its allocated error level, without requiring
      independent tests. It doesn't make approximate component procedures
      exact. Perfcheck applies this allocation to enabled metric gates.

   bootstrap
      Resampling observed data with replacement to approximate aspects of a
      statistic's sampling distribution. Perfcheck resamples run-level values
      separately within the current and baseline cohorts; more draws don't
      create more independent runs or cure selection bias.

   bootstrap replicate
      One statistic computed from one set of bootstrap resamples. A replicate
      is a simulation from the observed evidence, not a new experiment.

   CDF
      The cumulative distribution function :math:`F_X(x) = \Pr(X \leq x)`.

   central limit theorem
   CLT
      A convergence result for standardized sums or means. The classical IID
      finite-positive-variance version approaches a standard normal
      distribution; it doesn't say that individual observations are normal
      or that a fixed sample count always gives a good approximation.

   cohort
      The validated collection of usable per-run scalar inputs for one metric
      and one comparison side, together with its provenance and exclusions.

   comparability
      Suitability of observations for the same stated comparison. Perfcheck
      verifies configured policy and provenance constraints, but those checks
      don't establish environmental equivalence or causal comparability.

   conditional probability
      Probability after restricting to a conditioning event:
      :math:`\Pr(A\mid B)=\Pr(A\cap B)/\Pr(B)` when :math:`\Pr(B)>0`.

   confidence interval
      An interval-producing procedure whose coverage is defined over repeated
      sampling under specified assumptions. A frequentist 95% confidence
      level isn't a 95% posterior probability for a fixed parameter after
      observing one interval. Perfcheck's diagnostic percentile-bootstrap
      bounds don't promise exact confidence-interval coverage.

   confounder
      A factor that varies with the condition being compared and also affects
      the outcome, making attribution to that condition ambiguous.

   contention
      Competition for shared resources, such as CPU or network bandwidth,
      that can alter measurements and induce dependence between runs.

   convenience sample
      Observations selected because they are readily available rather than by
      a sampling design known to represent the population of interest.

   covariance
      :math:`\operatorname{Cov}(X,Y)=\operatorname{E}[(X-\operatorname{E}X)
      (Y-\operatorname{E}Y)]`, when defined. It measures joint linear
      variation and enters the variance of sums and differences. Zero
      covariance doesn't generally imply independence.

   coverage
      In measurement eligibility, retained point count divided by expected
      point count. In interval estimation, the repeated-sampling probability
      that an interval procedure contains its target parameter. These are
      different quantities; passing the first doesn't establish the second.

   degrees of freedom
      The number of free components after constraints in a statistical
      calculation. Deviations from a fitted sample mean sum to zero, leaving
      :math:`n-1` free components in the sample-variance calculation.

   density
   PDF
      A probability density function for an absolutely continuous variable.
      Its integral over an interval is the probability of that interval.
      Its height isn't a point probability and can exceed one.

   drift
      A change in the measurement-generating process over time, such as
      thermal or workload change. A scalar summary can conceal drift.

   effect size
      The magnitude of a contrast, such as a difference in means, in stated
      units or on a defined standardized scale. It isn't a significance
      measure. Perfcheck orients its mean difference so positive is worse.

   eligibility
      The configured data-quality and window requirements for a run metric
      to supply a finite scalar summary. An eligibility pass isn't proof of
      IID sampling, representativeness, or absence of confounding.

   equivalence
      A claim that an effect lies within prespecified acceptable bounds,
      supported by a suitable procedure and assumptions. Failing to reject
      a difference doesn't by itself establish equivalence.

   estimand
      The quantity an investigation targets, including its population and
      conditions; for example, a difference in mean per-run p95 latency.

   estimate
      The observed numerical result of applying an estimator to data.

   estimator
      A rule for using a sample to estimate an unknown quantity. Its output
      varies across repeated samples according to a sampling distribution.

   event
      A subset of a sample space, such as "at least eight heads in ten tosses."
      Its probability sums or integrates over its possible outcomes.

   exchangeability
      Invariance of a joint distribution under the relevant permutations of
      observations or labels. The required exchangeability must match the
      procedure; it isn't established by similar-looking histograms.

   expectation
      A population-level long-run average, written :math:`\operatorname{E}[X]`.

   experimental unit
      The entity independently assigned a condition in an experiment. Multiple
      measurements on one unit aren't automatically independent replications.

   family-wise error rate
   FWER
      The probability of at least one Type I error among a defined family of
      tests under the relevant configuration of true nulls and assumptions.

   family of tests
      The collection of inferential questions for which an error criterion
      is defined. Restricting attention to favorable results after looking
      at many questions doesn't remove the others from the selection process.

   false discovery rate
   FDR
      The expectation of the proportion of false rejections among all
      rejections, with proportion defined as zero when there are no
      rejections. It differs from family-wise error rate. Perfcheck doesn't
      offer a general FDR-control procedure.

   finite-population correction
      A factor reducing the standard error for simple random sampling
      without replacement from a fixed finite population. It isn't justified
      merely by collecting a large fraction of one run's scrape window.

   F-test
      In a two-variance comparison, a test based on a variance ratio whose
      usual F reference distribution assumes independent normal samples.
      It is sensitive to nonnormality and isn't a test of mean regression.

   Holm procedure
      A step-down family-wise procedure comparing ordered p-values to
      successively less stringent Bonferroni thresholds, stopping at the
      first nonrejection. Its error guarantee requires valid component
      p-values; perfcheck doesn't use this procedure.

   IID
      Independent and identically distributed: a modeling assumption, not a
      property inferred merely because values were collected in one run.

   independence
      For events, :math:`\Pr(A\cap B)=\Pr(A)\Pr(B)`; for random variables,
      the corresponding factorization for their joint probabilities.
      Independent events needn't be disjoint. Separate run IDs don't prove
      independent measurements.

   inference
      Reasoning from observed data to unknown quantities under assumptions
      about sampling or data generation, rather than merely describing data.

   law of large numbers
   LLN
      A convergence result for averages. Under IID sampling with finite
      expectation, the sample mean converges to that expectation. It doesn't
      correct a sample drawn from the wrong population.

   likelihood
      The probability mass or density of the observed data viewed as a
      function of a model's parameter. It isn't itself a probability
      distribution over parameter values.

   Mann--Whitney test
      A rank-based comparison of independent samples. A general
      distributional or ordering interpretation isn't automatically a
      comparison of medians; that interpretation needs additional assumptions.

   minimum detectable effect
      An effect size targeted by a design at specified power, alpha, and
      variability assumptions. It isn't an effect guaranteed to be detected
      or a magnitude inferred from a nonsignificant result.

   missingness
      The process by which observations or runs aren't available. Excluding
      missing evidence doesn't remove bias when missingness depends on the
      unobserved outcome or relevant conditions.

   Monte Carlo error
      Variation from approximating a calculation with finitely many random
      draws. More bootstrap draws can reduce this numerical variation but
      don't reduce the original experiment's sampling uncertainty.

   multiple testing
      Making several inferential decisions within a family or selection
      process. Error accounting must address the questions actually searched,
      not only the most favorable result eventually reported.

   normal distribution
      The symmetric bell-shaped distribution :math:`N(\mu,\sigma^2)` with
      mean :math:`\mu` and variance :math:`\sigma^2>0`. A normal sampling
      approximation for a mean doesn't imply normal raw observations.

   noninferiority
      A claim that deterioration is smaller than a prespecified acceptable
      margin, requiring an appropriate inferential procedure. A perfcheck
      PASS isn't a general noninferiority certificate.

   null hypothesis
      The parameter values or distributions under which a test calibrates
      extremeness and its Type I error. It isn't a conclusion established
      merely by failure to reject it.

   one-sided test
      A test whose alternative specifies a direction. Its extremeness rule
      and tail differ from a two-sided test and should be chosen in advance.

   optional stopping
      Letting observed results determine when to stop collecting evidence.
      Repeatedly using a fixed-sample test and stopping on significance
      needn't preserve its fixed-sample error level.

   outlier
      An observation unusually distant relative to a model or the rest of
      the data. It may be a real event rather than an error; distance alone
      doesn't justify deleting it.

   p95
      The 95th percentile, a quantile at probability 0.95. It has the
      measurement's units and isn't a p-value or a confidence level.

   p-value
      Under a specified null model, the probability of a test statistic at
      least as extreme as observed according to the chosen test rule. It
      isn't the probability that the null hypothesis is true, a measure of
      effect size, or a perfcheck bootstrap bound.

   paired design
      A design with meaningful prespecified matches between conditions.
      Paired analysis preserves those matches, often using within-pair
      differences. Perfcheck's cohort bootstrap is unpaired.

   parameter
      A fixed but generally unknown quantity in a statistical model.

   percentile
      A quantile position on a 0--100 scale; the 95th percentile corresponds
      to probability 0.95. Sample estimates depend on a quantile convention.

   permutation test
      A test comparing a statistic with its distribution under valid
      rearrangements of data or labels. The randomization design or null
      assumptions must justify those rearrangements.

   PMF
      A probability mass function assigning :math:`\Pr(X=k)` to each value
      of a discrete random variable. Its masses sum to one.

   population
      The broader collection about which a claim could be made.

   posterior
      A distribution over unknown quantities conditional on data and a
      specified prior and likelihood. It isn't obtained by subtracting a
      p-value from one, and isn't produced by perfcheck's comparison rule.

   power
      The probability that a specified test rejects its null under a
      specified alternative and design. It depends on effect, variability,
      sample size, alpha, and assumptions; it isn't the probability a
      particular observed result is correct.

   practical significance
      Whether an effect matters operationally, judged against a stated
      meaningful size rather than only statistical evidence. Perfcheck uses
      a policy practical threshold separately from its observed effect.

   precision
      The concentration of an estimator's repeated-sampling results, often
      described by its standard error. High precision doesn't imply low bias
      or an appropriate population.

   prior
      A distribution over unknown quantities specified before conditioning
      on the data in a Bayesian analysis.

   provenance
      The traceable origin of evidence and calculations, including source
      identities, hashes, intervals, policies, and numerical options. It
      supports auditing without proving statistical independence.

   pseudoreplication
      Treating dependent measurements on an experimental unit as if they
      were independent experimental repetitions, overstating information.

   quantile
      A value associated with a cumulative probability; a percentile expresses
      the same position using a 0--100 scale.

   random variable
      A numerical function of an uncertain outcome. A realized observation
      is a value of that variable, not its whole distribution.

   randomization
      Use of a random mechanism to assign experimental conditions or order.
      It reduces systematic assignment bias but doesn't guarantee balance
      or population representativeness in an individual experiment.

   realization
      One observed outcome of a measurement or random process.

   sample
      The finite observed values used to calculate a statistic.

   sample space
      The set of possible outcomes for a specified random procedure. Counting
      outcomes gives probability by a simple ratio only if they are equally
      likely.

   sampling distribution
      The distribution a statistic would have across repeated samples from the
      same specified procedure.

   selection bias
      Distortion from which observations enter the evidence set, such as
      retaining only runs that survived performance-dependent failures.

   standard deviation
   SD
      The square root of variance, describing spread in the original units.
      Sample SD describes observed spread; it isn't the standard error of
      the mean or a confidence interval.

   standard error
   SE
      The standard deviation of an estimator's sampling distribution.
      For an IID finite-variance sample mean it is :math:`\sigma/\sqrt{n}`,
      commonly estimated by :math:`s/\sqrt{n}`. Dependence changes that formula.

   statistic
      A number computed from observed data, such as a mean or quantile.

   statistical significance
      A test result meeting its prespecified rejection rule at a chosen
      level under its assumptions. It doesn't measure operational importance
      or establish causation.

   summary artifact
      The deterministic, source-hashed per-run artifact that records metric
      availability, eligibility evidence, and selected scalar summaries.

   survival function
      Here :math:`S(x)=\Pr(X>x)=1-F_X(x)`. For a discrete distribution,
      :math:`\Pr(X\geq x)` additionally includes any point mass at :math:`x`.

   tail probability
      The probability beyond a specified threshold in a distribution. Whether
      the threshold is included matters for discrete variables. A test's
      p-value uses the tail or extremeness set defined by that test.

   t distribution
      A symmetric reference distribution with a degrees-of-freedom
      parameter and heavier tails than a standard normal. It arises exactly
      for a standardized normal-sample mean with estimated variance, and
      approximately in procedures such as Welch's test.

   t-test
      A mean-comparison test using a t reference distribution under stated
      assumptions. One-sample, paired, pooled two-sample, and Welch versions
      answer different design-specific questions.

   test statistic
      A data-derived quantity used to order evidence against a null model.
      Its null distribution and the alternative determine extremeness.

   two-sided test
      A test allowing departures in either direction. Its p-value requires
      a stated extremeness rule; it isn't universally twice a one-sided value.

   Type I error
      Rejecting a true null hypothesis in a specified testing procedure.

   Type II error
      Not rejecting the null when a specified alternative is true. Its
      probability depends on that alternative, not just the chosen alpha.

   uniform distribution
      A continuous distribution with constant density over a specified
      interval. Equal density doesn't mean positive probability at individual
      points, or follow just from knowing upper and lower bounds.

   unpaired design
      A comparison with no meaningful one-to-one matching between conditions.
      Perfcheck resamples the two cohorts independently; ordering their
      artifacts doesn't create a paired analysis.

   variance
      Expected squared distance from expectation; its square root is the
      standard deviation.

   warmup
      An initial transient before the intended measurement state, such as
      cache filling. Time-based trimming can omit a known transient without
      proving that the retained window is stationary.

   Welch's test
      An unpaired comparison of two means that permits unequal variances,
      using separate variance estimates and approximate degrees of freedom.
      It still needs independent samples and suitable distributional
      conditions; it isn't perfcheck's comparison procedure.

   within-run variation
      Variation among measurements during one run. More within-run points
      don't automatically provide more independent run-level replications.

   z-test
      A test using a standard normal reference statistic. For a normal mean
      with known population variance, the standardized mean gives an exact
      reference; replacing unknown variance or changing the model needs a
      separate justification.
