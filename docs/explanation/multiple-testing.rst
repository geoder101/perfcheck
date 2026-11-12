Multiple testing
================

Prerequisites are :doc:`probability-and-distributions` and
:doc:`inference-and-power`: in particular, a valid p-value satisfies
:math:`\Pr(P\leq u)\leq u` under its null. Read :doc:`experimental-design`
alongside this chapter, because choosing the family of questions is part of
design, not an arithmetic correction after finding an interesting result.

Why one error rate doesn't describe many chances
------------------------------------------------

Suppose 20 independent tests all concern true nulls, and each rejects with
probability exactly :math:`\alpha=0.05`. The probability that none rejects is
the product of the 20 non-rejection probabilities. Therefore

.. math::

   \Pr(\text{at least one false rejection})
    =1-\Pr(\text{no false rejections})
    =1-(1-\alpha)^m
    =1-0.95^{20}\approx0.641514.

This is a 64% family-wise error rate (FWER), not a 64% probability that a
particular finding is false. The equality assumes independence and exact
per-test size; conservative discrete tests need not attain it. Correlated
metrics don't obey this product formula automatically.

Let :math:`V` count false rejections among the family. FWER is
:math:`\Pr(V\geq1)`. It asks whether even one false claim occurs. That is a
reasonable target for a small family of release gates, but not the only possible
error criterion for a large exploratory screen.

Bonferroni from the union bound
------------------------------------

Let :math:`I_0` index the true nulls among :math:`m` predeclared tests.
Reject test :math:`i` when :math:`P_i\leq\alpha/m`. Then

.. math::

   \Pr(V\geq1)
    &=\Pr\left(\bigcup_{i\in I_0}\{P_i\leq\alpha/m\}\right)\\
    &\leq\sum_{i\in I_0}\Pr(P_i\leq\alpha/m)\\
    &\leq |I_0|\alpha/m\leq\alpha.

The first inequality is the union bound. It needs no independence; the second
needs valid marginal p-values under each true null. Adjusting invalid inputs
doesn't make them valid. Equivalently, report Bonferroni adjusted p-values
:math:`\widetilde p_i=\min(1,mp_i)` and compare them with the family alpha.
An adjusted p-value is a procedure-specific threshold summary, not the posterior
probability that the hypothesis is true.

Holm: stop at the first failure
------------------------------------

Holm orders the observed values :math:`p_{(1)}\leq\cdots\leq p_{(m)}` and
compares them successively with :math:`\alpha/(m-i+1)`. Reject while each
comparison succeeds. At the first failure, stop and retain that null and all
later nulls. Equality counts as rejection in this teaching convention.

For five fixed p-values at :math:`\alpha=0.05`:

.. list-table:: A fixed family, already sorted
   :header-rows: 1

   * - Hypothesis
     - Raw p
     - Holm threshold
     - Holm result
     - Holm adjusted p
   * - A
     - 0.004
     - 0.010000
     - Reject
     - 0.020
   * - B
     - 0.012
     - 0.012500
     - Reject
     - 0.048
   * - C
     - 0.018
     - 0.016667
     - Stop; don't reject
     - 0.054
   * - D
     - 0.030
     - 0.025000
     - Don't reject after stop
     - 0.060
   * - E
     - 0.200
     - 0.050000
     - Don't reject after stop
     - 0.200

The adjusted values are the cumulative maxima

.. math::

   \widetilde p_{(i)}^{\mathrm{Holm}}
    =\min\left(1,\max_{j\leq i}(m-j+1)p_{(j)}\right).

The maximum preserves the stop rule. Unsort these values to attach them to the
original hypotheses. Ordinary Bonferroni would reject only A in this example,
with adjusted values :math:`(0.020,0.060,0.090,0.150,1)`.

Why does Holm control FWER without independence? If any true null is rejected,
consider the first true null in the sorted sequence. With :math:`m_0` true
nulls, its rank :math:`i` is at most :math:`m-m_0+1`. Its rejection thus requires
a true-null p-value at most :math:`\alpha/(m-i+1)\leq\alpha/m_0`.
The union bound over the :math:`m_0` true nulls bounds the probability of this
event by alpha. This argument works for any configuration of true and false
nulls, provided each true-null p-value is valid.

False discovery rate answers a different question
------------------------------------------------------

Let :math:`R` be the total number of rejections. The realized false discovery
proportion and its expectation are

.. math::

   \mathrm{FDP}=\frac{V}{\max(R,1)},\qquad
   \mathrm{FDR}=\operatorname{E}(\mathrm{FDP}).

The denominator convention makes FDP zero when nothing is rejected. FDR is an
average over repeated datasets. Controlling it at 5% doesn't guarantee at most
5% false discoveries in every observed list, doesn't give each item a 5% chance
of being false, and isn't generally the ratio :math:`\operatorname{E}(V)/
\operatorname{E}(R)`. When every null is true, FDP is one whenever there is
any rejection, so FDR equals FWER in that special case.

Benjamini-Hochberg (BH) at target :math:`q` finds the largest rank :math:`k`
such that :math:`p_{(k)}\leq kq/m`, then rejects all ranks through :math:`k`.
If no rank qualifies, reject none. Unlike Holm, this is a step-up rule: don't
stop at the first failed comparison. For the same five values and :math:`q=0.05`,
the thresholds are :math:`(0.01,0.02,0.03,0.04,0.05)`. The largest qualifying
rank is four, so A through D are rejected. The adjusted values are

.. math::

   \widetilde p_{(i)}^{\mathrm{BH}}
    =\min\left(1,\min_{j\geq i}\frac{m}{j}p_{(j)}\right),

which gives :math:`(0.020,0.030,0.030,0.0375,0.200)`. The reverse cumulative
minimum enforces the step-up rule. These values aren't interchangeable with
Holm's adjusted p-values because the error criterion differs.

The standard BH guarantee is :math:`\mathrm{FDR}\leq q\,m_0/m\leq q` under
independent valid p-values, with extensions under suitable positive regression
dependence on the true nulls (PRDS). PRDS is a specific mathematical condition,
not merely an informal observation that metrics are positively correlated.
Ordinary BH doesn't have this guarantee under arbitrary dependence.
The Benjamini-Yekutieli modification replaces :math:`q` by :math:`q/H_m`, where
:math:`H_m=\sum_{j=1}^m1/j`, for a more conservative arbitrary-dependence
guarantee with valid p-values. Choosing an error criterion is a scientific and
operational decision, not permission to select whichever method rejects most.

Selection and repeated looks enlarge the experiment
----------------------------------------------------

A family may include several metrics, workloads, time windows, transformations,
subgroups, model choices and interim looks. Reporting only the smallest p-value
after trying all of them doesn't make this a one-test experiment. Even a
predeclared Bonferroni correction over metrics doesn't cover uncounted repeated
looks at accumulating data. With independent, fresh level-0.05 tests, the same
product calculation above already shows the risk; overlapping looks are
dependent and require their own analysis rather than that exact formula.

Decide the confirmatory family and stopping rule before collecting evidence.
For planned interim looks, use a justified sequential design or alpha-spending
scheme. Exploratory findings can motivate an independent confirmation, but the
held-out data must not have guided the selection. Changing the baseline until
a comparison passes is also selection, even if every individual comparison is
reproducible. See :doc:`experimental-design` for run allocation and stopping.

What perfcheck actually allocates
--------------------------------------

Perfcheck fixes nominal alpha at 0.05 and uses :math:`0.05/m` for every enabled
policy metric, including metrics that later become ``INCONCLUSIVE``. Disabled
metrics don't enter :math:`m`. Allocation isn't redistributed after eligibility
filtering. The effective alpha selects a lower bootstrap percentile, not a
computed p-value. Holm, BH and their adjusted p-values above are teaching
methods, not product features.

Bonferroni's theorem explains a nominal allocation strategy; it doesn't prove
that perfcheck's percentile-bootstrap bounds attain their nominal error rates.
Such a conclusion additionally requires calibrated individual procedures under
the actual sampling design. The product doesn't establish that premise, nor
does its allocation cover ad-hoc metrics or repeated invocations. Read
:doc:`uncertainty-and-comparison` for the numerical contract and
:doc:`decisions-and-limitations` for the resulting verdicts.

Next, contrast the models in :doc:`comparative-methods` and
`Lab 10 <https://github.com/geoder101/perfcheck/blob/main/examples/10-comparative-methods.py>`_. Return to
`Lab 08 <https://github.com/geoder101/perfcheck/blob/main/examples/08-bootstrap-and-decisions.py>`_ to inspect
the fixed product rule without importing an exploratory testing procedure.
