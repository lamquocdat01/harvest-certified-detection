"""Macros for the exploratory Q2 paragraph (outcome (b) of the P4 prompt: E1-E3 all FAIL, narrow claim kept).
Every number comes from results/exploratory_q2_test.json and exploratory_q2_boot_test.json."""
from __future__ import annotations


def e_macros(X, XB):
    E1, E2, E3 = X["E1"], X["E2"], X["E3"]
    p = E2["predictors"]["T1_both_abar (primary)"]
    a0 = E3["per_amax_d0"]
    ratio = E2["a_bar_K_over_blk_median"]
    hk = XB["holm_E1_K_minus_perabar"]
    src = "exploratory_q2_test.json / exploratory_q2_boot_test.json"
    nfeas = f"{E3['n_feasible']:,}".replace(",", "{,}")
    pc = lambda v: f"{100 * v:.1f}\\,\\%"  # noqa: E731
    sec = (
        r"\subsection{Exploratory: what helps instead}"
        "\n"
        r"A Kansal-style predictive duty cycle~\cite{kansal2007} did beat blackout on TEST "
        f"(median {E2['d_obs_median']:+.3f}). "
        r"We registered three follow-up predictions before running a dedicated post-test stage; "
        r"all three failed, so the result is reported as an observation only (Figs.~\ref{fig:q2} and~\ref{fig:q2b}). "
        f"The controller spends spilled energy (median mean activation {ratio:.2f} times that of blackout), "
        r"but at equal mean activation it is indistinguishable from periodic operation "
        f"(median difference {E1['d_K_minus_perabar']['median']:+.4f}, with the predicted sign in only "
        f"{pc(E1['share_ge_-0.005'])} of cases and the opposite sign significant in {hk['n_sig_wrong_sign']} of "
        f"{hk['n']} cells). "
        r"Its gain is also far smaller than the difference of the two floors "
        f"(median {p['median_pred']:+.3f} predicted, $R^2={p['R2_45']:.1f}$ around the identity line), "
        r"because it concentrates activations in daytime and still has outages, so it pays the Jensen gap of "
        r"Corollary~\ref{cor:jensen} and the outage term of Proposition~\ref{prop:blackout}. "
        r"A constant rate sized on the TRAIN months to never black out did worse than both "
        f"(median {a0['median_minus_blk']:+.2f} against blackout, better than both in {pc(a0['share_le_both'])} of "
        f"{nfeas} cases). "
        r"Theorem~\ref{thm:energy} bounds schedules that never empty storage; on these traces, accepting short "
        r"outages and spending the surplus is the better operating point."
        "\n"
        r"\begin{figure}[!t]\centering"
        r"\includegraphics[width=\columnwidth]{figures/F6p_throttle_kansal_amax_test.pdf}"
        r"\caption{Miss relative to blackout against capacity (medians over the TEST cases in which periodic "
        r"$K=8$ has outages). Exploratory (post-test) analysis.}\label{fig:q2}\end{figure}"
        "\n"
        r"\begin{figure}[!t]\centering"
        r"\includegraphics[width=\columnwidth]{figures/F7_kansal_obs_vs_pred_test.pdf}"
        r"\caption{Observed Kansal--blackout miss difference against the difference of the two floors "
        r"(Theorem~\ref{thm:floor}); points above the dashed line gain less than the floors suggest. "
        r"Exploratory (post-test) analysis.}\label{fig:q2b}\end{figure}"
    )
    abstract = (r"a predictive controller that spends spilled energy misses fewer events "
                f"(median {E2['d_obs_median']:+.3f}), a post-test observation whose registered explanations "
                r"were not confirmed.")
    return {"Esection": (sec, src), "EabstractSentence": (abstract, src)}
