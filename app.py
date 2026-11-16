import csv
import io
import streamlit as st
from odds_comparison import compare_row, PROJECTION_NOTE
from pregame_feed import upcoming_games
from player_projections import projections
from engine import market_probability, implied_probability, expected_value, devig_two_way

st.set_page_config(page_title='EDGE AI | Probability Lab', page_icon='📈', layout='wide')
st.title('EDGE AI — Probability Lab')
st.caption('v0.1 | Transparent statistical baseline • NOT trained, calibrated, or validated • No live odds feed')
st.warning('Model probabilities depend entirely on the mean and uncertainty used by the calculator. Positive EV is not a verified betting edge until projections are validated on unseen games.')

tabp, tab0, tab1, tab2, tab3 = st.tabs(['Automatic player projections','Upcoming games (automatic)','Single-market calculator','Multi-book CSV scanner','Model roadmap'])
with tabp:
    st.subheader('Pregame player projections — experimental')
    st.warning('These are recent-game weighted averages, NOT calibrated probabilities, picks, or verified betting edges. Anytime touchdown rows show a recent-game scoring frequency (0 to 1), NOT a validated probability. Passing TDs are excluded. Missing box-score rows, injuries, starting status, and sportsbook lines are not accounted for.')
    league = st.selectbox('Sport', ['NBA', 'NFL'], key='projection_league')
    @st.cache_data(ttl=3600, show_spinner=False)
    def cached_projections(sport):
        games = upcoming_games(sport)
        return games, projections(sport, games)
    if st.button('Load automatic projections', type='primary'):
        st.session_state.pop('loaded_projections', None)
        try:
            with st.spinner('Retrieving recent box scores and calculating projections...'):
                games, estimates = cached_projections(league)
            st.session_state['loaded_projections'] = (league, len(games), estimates)
        except Exception as exc:
            st.error(f'Unable to load projections: {exc}')
    loaded = st.session_state.get('loaded_projections')
    if loaded and loaded[0] == league:
        _, game_count, estimates = loaded
        st.write(f'Upcoming games found: {game_count}')
        if estimates:
            st.dataframe(estimates, use_container_width=True, hide_index=True)
            st.caption('Projection = weighted average of up to five recently available game box scores. Sample coverage can be incomplete; missing games or injured players may bias results. Refresh cache every hour.')
            template = io.StringIO()
            fields = ['sport', 'event', 'team', 'player', 'stat', 'market', 'selection',
                      'line', 'mean', 'sd', 'distribution', 'sportsbook', 'odds',
                      'opposing_odds', 'projection_source', 'games_sampled']
            writer = csv.DictWriter(template, fieldnames=fields)
            writer.writeheader()
            for estimate in estimates:
                if estimate['Market'].startswith('Anytime touchdown'):
                    continue
                writer.writerow({
                    'sport': league, 'team': estimate['Team'], 'player': estimate['Player'],
                    'stat': estimate['Market'], 'market': 'player_prop',
                    'mean': estimate['Projection'], 'distribution': 'Normal',
                    'projection_source': 'recent_box_scores',
                    'games_sampled': estimate['Games sampled'],
                })
            st.download_button('Download stat projections for CSV comparison',
                               template.getvalue(), 'projection_comparison.csv', 'text/csv')
            st.caption('Match each player and stat to the intended game. Fill in the event, selection, line, standard deviation, book and prices before uploading in the CSV scanner. Anytime touchdown frequencies are excluded from this template.')
        else:
            st.info('No eligible recent player box scores found for upcoming teams. This is not a zero projection.')
with tab0:
    st.subheader('Automatic pregame schedule')
    st.info('This is the first data-automation milestone: upcoming games only. Player prop predictions are NOT generated yet. This public feed may change or be unavailable.')
    selected = st.selectbox('League', ['NFL','NBA','MLB'], key='auto_sport')
    @st.cache_data(ttl=900, show_spinner=False)
    def get_schedule(league):
        return upcoming_games(league)
    try:
        schedule = get_schedule(selected)
        if schedule:
            st.dataframe(schedule, use_container_width=True, hide_index=True)
        else:
            st.info('No upcoming games found in the next seven days.')
        st.caption('Schedule cache refreshes every 15 minutes while the app is running. No sportsbook odds or player projections are connected.')
    except Exception as exc:
        st.error(f'Unable to retrieve schedule: {exc}')
with tab1:
    c1,c2,c3=st.columns(3)
    sport=c1.selectbox('Sport',['NBA','NFL','MLB','Other'])
    market=c2.selectbox('Market',['player_prop','moneyline','spread','total'])
    distribution=c3.selectbox('Distribution',['Normal','Poisson'],help='Poisson works for nonnegative count props/totals only')
    name=st.text_input('Market description','Example: Player points')
    a,b,c,d=st.columns(4)
    side=a.selectbox('Selection',['over','under'],help='Moneyline: over=home, under=away. Spread: over=home covers, under=away covers.')
    line=b.number_input('Line (home spread for spreads)',value=24.5,step=0.5)
    mean=c.number_input('Your projected mean',value=25.0,step=0.5)
    sd=d.number_input('Projected standard deviation',value=6.0,min_value=0.01,step=0.5,disabled=(distribution=='Poisson'))
    odds=st.number_input('Sportsbook American odds',value=-110,step=5)
    if st.button('Calculate',type='primary'):
        try:
            p=market_probability(market,side,line,mean,sd,distribution)
            cols=st.columns(3)
            cols[0].metric('Model probability',f'{p:.1%}')
            cols[1].metric('Book implied probability',f'{implied_probability(odds):.1%}')
            cols[2].metric('Expected return per $1 staked',f'{expected_value(p,odds):+.1%}')
            st.caption('These are conditional outputs of the assumptions above, not evidence of predictive accuracy.')
        except ValueError as exc: st.error(str(exc))
with tab2:
    st.write('Upload manually recorded odds or complete the CSV template from Automatic player projections. Enter opposing_odds from the same book, event, market, line and snapshot. For spreads, record the home spread. For moneylines, enter 0 as the line.')
    st.caption('Model edge is model probability minus the no-vig book probability, in percentage points. Expected return uses the offered price. Odds are manually imported.')
    upload = st.file_uploader('Upload odds CSV', type='csv')
    if upload:
        try:
            reader = csv.DictReader(io.StringIO(upload.getvalue().decode('utf-8-sig')))
            if not reader.fieldnames:
                raise ValueError('CSV is missing a header.')
            out = [
                compare_row(row, row_number)
                for row_number, row in enumerate(reader, start=1)
            ]
            if not out:
                st.info('The CSV has no data rows.')
            else:
                out.sort(key=lambda row: (row['expected_return'] is not None,
                                          row['expected_return'] or 0), reverse=True)
                incomplete = sum(bool(row['warning']) for row in out)
                if incomplete:
                    st.warning(f'{incomplete} row(s) have missing or invalid inputs. See the Warning column.')
                if any(row.get('projection_source') == 'recent_box_scores' for row in out):
                    st.warning(PROJECTION_NOTE)
                columns = {
                    'mean': st.column_config.NumberColumn('Projection'),
                    'line': st.column_config.NumberColumn('Book line'),
                    'no_vig_probability_pct': st.column_config.NumberColumn('No-vig implied probability (%)', format='%.2f'),
                    'model_edge_pp': st.column_config.NumberColumn('Model edge (pp)', format='%+.2f'),
                    'warning': st.column_config.TextColumn('Warning'),
                }
                first = [key for key in ('csv_row', 'sport', 'event', 'player', 'stat',
                                         'sportsbook', 'market', 'selection', 'mean', 'line',
                                         'no_vig_probability_pct', 'model_edge_pp', 'warning')
                         if key in out[0]]
                st.dataframe(out, column_config=columns,
                             column_order=first + [key for key in out[0] if key not in first],
                             use_container_width=True, hide_index=True)
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=out[0].keys())
                writer.writeheader()
                writer.writerows(out)
                st.download_button('Download comparison results', buf.getvalue(),
                                   'edge_ai_ranked.csv', 'text/csv')
        except (UnicodeError, csv.Error, ValueError) as exc:
            st.error(f'Could not parse CSV: {exc}')
with tab3:
    st.markdown('''**Next milestones**\n\n1. Import timestamped historical games and prop outcomes, with injury/lineup information available before tipoff.\n2. Train separate sport/market models using walk-forward time splits.\n3. Evaluate Brier score, log loss, calibration curves, and results against no-vig sportsbook baselines.\n4. Add legal, reliable odds feeds and scheduled updates, then track closing-line value.\n5. Implement authentication, subscription billing, and data-provider/commercial licensing checks.\n\n**Market conventions:** Moneyline `over` = home win; `under` = away win. Spread `over` = home margin exceeds negative home spread. Integer-line pushes in Normal are approximated as zero probability; Poisson count pushes are removed conditionally.\n''')
    st.write('Two-way proportional no-vig calculator')
    x,y=st.columns(2)
    home=x.number_input('Side A odds',value=-110,key='h')
    away=y.number_input('Side B odds',value=-110,key='a')
    try:
        pa,pb=devig_two_way(home,away)
        st.write(f'No-vig implied probabilities: A {pa:.2%}, B {pb:.2%}')
    except ValueError as exc:st.error(str(exc))
