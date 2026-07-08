import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE = "#3987e5"
RED = "#e66767"
MUTED = "#7c7a74"

st.set_page_config(page_title="Which Ads Actually Deserve the Credit?", layout="wide")


@st.cache_data
def load_data():
    markov = pd.read_csv("data/markov_attribution.csv")
    lt = pd.read_csv("data/last_touch_baseline.csv")
    markov["channel"] = markov["channel"].astype(str)
    lt["channel"] = lt["channel"].astype(str)

    markov = markov.sort_values("attribution_share", ascending=False).reset_index(drop=True)
    markov["markov_rank"] = markov.index + 1
    lt = lt.sort_values("last_touch_share", ascending=False).reset_index(drop=True)
    lt["lt_rank"] = lt.index + 1

    merged = markov.merge(lt, on="channel", how="inner")
    merged = merged.rename(columns={"attribution_share": "markov_share", "last_touch_share": "lt_share"})

    top = merged.sort_values("markov_share", ascending=False).head(15).copy()
    top["idx"] = (top["markov_share"] / top["lt_share"] - 1) * 100
    top = top.reindex(top["idx"].abs().sort_values(ascending=False).index).reset_index(drop=True)
    return top


df = load_data()

st.markdown(
    """
    <div style='text-align:center; padding: 12px 0 20px;'>
      <div style='color:#3987e5; font-weight:700; letter-spacing:0.14em;
                  font-size:11px; text-transform:uppercase;'>Marketing Budget Review</div>
      <h1 style='margin: 12px 0 14px;'>Which Ads Actually Deserve the Credit?</h1>
      <p style='max-width:640px; margin:0 auto; color:#b3b1a9; font-size:15px; line-height:1.6;'>
        Most companies give a sale's entire credit to the last ad someone saw &mdash; even if
        several other ads helped get them there. We re-split the credit fairly across every
        ad on the path, across 675 campaigns. Here's where the old method gets it wrong, and
        which campaigns should get more (or less) budget as a result.
      </p>
      <div style='color:#7c7a74; font-size:11px; text-transform:uppercase; letter-spacing:0.06em; margin-top:18px;'>
        16.5 Million Ads Shown &middot; 6.14 Million Customer Journeys
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

over_credited = int((df["idx"] < -1).sum())
best = df.loc[df["idx"].idxmax()]
worst = df.loc[df["idx"].idxmin()]

col1, col2, col3 = st.columns(3)
col1.metric("Campaigns getting too much credit", f"{over_credited} / 15")
col1.caption(
    f"{over_credited} of the 15 biggest campaigns are getting more credit — "
    "and more budget — than they've actually earned"
)
col2.metric("Biggest hidden winner", f"+{best['idx']:.1f}%")
col2.caption(
    f"Campaign {best['channel']} quietly helps close more sales than it gets credit for. "
    f"Old method ranks it #{int(best['lt_rank'])}; the fair method ranks it #{int(best['markov_rank'])}"
)
col3.metric("Most overrated campaign", f"{worst['idx']:.1f}%")
col3.caption(
    f"Campaign {worst['channel']} is riding on credit it didn't fully earn. "
    "Fair credit suggests cutting its budget"
)

st.subheader("Who deserves more (or less) budget")
st.caption("Comparing the old way of crediting sales to the fair way · biggest gaps first")

legend_col1, legend_col2 = st.columns([1, 8])
with legend_col1:
    st.markdown(
        f"<span style='color:{BLUE}'>&#9632;</span> Deserves more budget"
        f"&nbsp;&nbsp;&nbsp;<span style='color:{RED}'>&#9632;</span> Deserves less budget",
        unsafe_allow_html=True,
    )

labels = [f"Campaign {c}<br><span style='font-size:10px;color:#7c7a74'>Now #{mr} · was #{lr}</span>"
          for c, mr, lr in zip(df["channel"], df["markov_rank"], df["lt_rank"])]
colors = [BLUE if v >= 0 else RED for v in df["idx"]]

fig = go.Figure(
    go.Bar(
        x=df["idx"],
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in df["idx"]],
        textposition="outside",
        textfont=dict(color="#f5f5f4"),
        customdata=df[["markov_share", "lt_share"]].values * 100,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Fair credit: %{customdata[0]:.2f}%<br>"
            "Old credit: %{customdata[1]:.2f}%<br>"
            "Budget change needed: %{x:+.1f}%<extra></extra>"
        ),
    )
)
fig.update_layout(
    yaxis=dict(autorange="reversed", showgrid=False),
    xaxis=dict(
        title="Budget change needed",
        ticksuffix="%",
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor=MUTED,
        gridcolor="#2a2c30",
    ),
    plot_bgcolor="#16181c",
    paper_bgcolor="#0a0b0d",
    font_color="#f5f5f4",
    height=560,
    margin=dict(l=10, r=60, t=20, b=40),
)
st.plotly_chart(fig, use_container_width=True)

if st.checkbox("Show table view"):
    table = df[["channel", "markov_share", "lt_share", "idx", "markov_rank", "lt_rank"]].copy()
    table["markov_share"] = (table["markov_share"] * 100).round(2).astype(str) + "%"
    table["lt_share"] = (table["lt_share"] * 100).round(2).astype(str) + "%"
    table["idx"] = table["idx"].round(1).astype(str) + "%"
    table.columns = ["Campaign", "Fair credit", "Old credit", "Budget change needed", "Fair rank", "Old rank"]
    st.dataframe(table, use_container_width=True, hide_index=True)

st.caption(
    "How to read this: the old method (\"last-touch\") gives a sale's entire credit to the very "
    "last ad someone saw before buying. The fair method looks at everything someone saw along "
    "the way and splits the credit accordingly. When the fair method gives a campaign more "
    "credit than the old method did, that campaign is under-funded today — and vice versa. "
    "Shown here: the 15 biggest campaigns by fair credit, out of 675 total."
)
