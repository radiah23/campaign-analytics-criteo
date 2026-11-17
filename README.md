# Which Ads Actually Deserve the Credit?

**Markov-chain multi-touch attribution on 16.5 million Criteo ad impressions, compared against last-touch attribution.**

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)

Most companies give a sale's entire credit to the last ad a customer saw, even when several earlier ads helped. That rule quietly shapes budgets: campaigns that close sales look great, while campaigns that start journeys look useless. This project rebuilds every customer journey in the Criteo attribution dataset, models them as a Markov chain, and re-splits the credit for each conversion across every campaign on the path. A Streamlit dashboard then shows which campaigns are over- or under-credited by the old rule.

---

## The question

For each of 675 ad campaigns: **how much of the credit it gets under last-touch attribution has it actually earned**, and which campaigns should get more (or less) budget as a result?

## Approach

1. **Load** the raw Criteo file into SQLite (`scripts/convert_to_sqlite.py`) so 16.5M rows can be queried without loading everything into memory at once.
2. **Rebuild journeys** (`scripts/markov_attribution.py`): group impressions by user, order them by timestamp, and turn each user into a path such as `start → campaign A → campaign B → conversion` (or `→ null`). That gives about 6.14M customer journeys.
3. **Fit a first-order Markov chain**: count transitions between campaigns and convert them to probabilities.
4. **Compute removal effects**: for each campaign, delete it from the graph and measure how much the overall probability of reaching `conversion` drops. A campaign's share of all removal effects is its fair share of credit.
5. **Baseline**: compute standard last-touch credit from the same paths.
6. **Compare**: for the 15 largest campaigns, the gap between the two methods is an index of over- or under-crediting.

## Key findings (top 15 campaigns)

- **12 of the 15 biggest campaigns get more credit under last-touch than the Markov model says they earned**, so they are likely over-funded.
- **Biggest hidden winner: campaign 17686799** earns about **33% more** credit under the Markov model. Last-touch ranks it **#20**; the Markov model ranks it **#10**. It helps start journeys that other campaigns finish.
- **Most overrated: campaign 9100692**, credited about **26% less** under the Markov model (#10 under last-touch, #15 under Markov).
- The top campaign (10341182) stays #1 under both methods, but its share still drops by about 16%: credit is spread more evenly once the earlier touchpoints count.

## Dashboard

`app.py` is a Streamlit app built for a non-technical marketing audience. It shows three headline metrics (over-credited campaigns, biggest hidden winner, most overrated campaign) and a diverging bar chart of the credit gap for each top campaign. A static HTML version is in `dashboard/attribution-dashboard.html`.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The results CSVs are included in `data/`, so the dashboard runs without the raw data. The repo also includes a dev container config, so it opens and runs directly in GitHub Codespaces.

## Reproducing the attribution from raw data

```bash
# 1. Download the Criteo Attribution Modeling for Bidding dataset and place the file in data/raw/
#    (requirements.txt includes kagglehub for downloading it)
# 2. Load it into SQLite → data/criteo.db
python scripts/convert_to_sqlite.py
# 3. Rebuild paths, fit the Markov chain, compute removal effects and the last-touch baseline
python scripts/markov_attribution.py   # writes data/markov_attribution.csv and data/last_touch_baseline.csv
```

## Repository structure

```
├── app.py                         # Streamlit dashboard
├── scripts/
│   ├── convert_to_sqlite.py       # raw TSV → SQLite
│   └── markov_attribution.py      # paths, Markov chain, removal effects, last-touch baseline
├── data/
│   ├── markov_attribution.csv     # removal effect + attribution share per campaign (675 rows)
│   └── last_touch_baseline.csv    # last-touch share per campaign (675 rows)
├── dashboard/attribution-dashboard.html
└── requirements.txt
```

## Limitations

- A first-order Markov chain only looks one step back; higher-order chains or Shapley-value attribution could capture longer interactions between campaigns.
- Removal effects measure contribution to conversion probability, not incremental revenue. Holdout experiments would be needed to confirm causal lift.

## Author

**Radiah Khan** · [Portfolio](https://radiah23.github.io) · [LinkedIn](https://www.linkedin.com/in/radiah-khan/)

Data: Criteo AI Lab, *Criteo Attribution Modeling for Bidding Dataset*.
