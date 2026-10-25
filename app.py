import csv
import io
import streamlit as st
from pregame_feed import upcoming_games
from player_projections import projections
from engine import market_probability, implied_probability, expected_value, devig_two_way

st.set_page_config(page_title='EDGE AI | Probability Lab', page_icon='📈', layout='wide')
st.title('EDGE AI — Probability Lab')
st.caption('v0.1 | Transparent statistical baseline • NOT trained, calibrated, or validated • No live odds feed')
st.warning('Model probabilities depend entirely on the mean and uncertainty you supply. Positive EV is not a verified betting edge until projections are validated on unseen games.')

tabp, tab0, tab1, tab2, tab3 = st.tabs(['Automatic player projections','Upcoming games (automatic)','Single-market calculator','Multi-book CSV scanner','Model roadmap'])
with tabp:
    st.subheader('Pregame player projections — experimental')
    st.warning('These are recent-game weighted averages, NOT calibrated probabilities, picks, or verified betting edges. Injuries, starting status, and sportsbook lines are not accounted for.')
    league = st.selectbox('Sport', ['NBA', 'NFL'], key='projection_league')
    @st.cache_data(ttl=3600, show_spinner=False)
    def cached_projections(sport):
        games = upcoming_games(sport)
        return games, projections(sport, games)
    if st.button('Load automatic projections', type='primary'):
        try:
            with st.spinner('Retrieving recent box scores and calculating projections...'):
                games, estimates = cached_projections(league)
            st.write(f'Upcoming games found: {len(games)}')
            if estimates:
                st.dataframe(estimates, use_container_width=True, hide_index=True)
                st.caption('Projection = weighted average of up to five recently available game box scores. Sample coverage can be incomplete; missing games or injured players may bias results. Refresh cache every hour.')
            else:
                st.info('No eligible recent player box scores found for upcoming teams. This is not a zero projection.')
        except Exception as exc:
            st.error(f'Unable to load projections: {exc}')
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
    st.write('Upload a CSV with one row per sportsbook selection. Required columns: sport, market, selection, line, mean, sd, distribution, sportsbook, odds. Optional: event, player. All rows use YOUR assumed projections.')
    upload=st.file_uploader('Upload odds CSV',type='csv')
    if upload:
        try:
            rows=list(csv.DictReader(io.StringIO(upload.getvalue().decode('utf-8-sig'))))
            out=[]
            for r in rows:
                try:
                    p=market_probability(r['market'],r['selection'],float(r['line']),float(r['mean']),float(r['sd']),r['distribution'])
                    out.append({**r,'model_probability':round(p,4),'implied_probability':round(implied_probability(int(r['odds'])),4),'expected_return':round(expected_value(p,int(r['odds'])),4)})
                except (ValueError,KeyError,ZeroDivisionError) as exc:
                    st.warning(f'Skipped row: {exc}')
            out.sort(key=lambda r:r['expected_return'],reverse=True)
            st.dataframe(out,use_container_width=True)
            if out:
                buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=out[0].keys());writer.writeheader();writer.writerows(out)
                st.download_button('Download ranked results',buf.getvalue(),'edge_ai_ranked.csv','text/csv')
        except Exception as exc: st.error(f'Could not parse CSV: {exc}')
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
