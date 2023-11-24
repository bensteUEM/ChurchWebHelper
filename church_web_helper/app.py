import logging
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, session, send_file, url_for

from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from communi_api.communi_api import CommuniApi
from communi_api.churchToolsActions import delete_event_chats, create_event_chats, get_x_day_event_ids, generate_group_name_for_event
from communi_api.communiActions import get_create_or_delete_group
from flask_session import Session

app = Flask(__name__)
app.secret_key = os.urandom(16)

config = {"SESSION_PERMANENT": False,
          "SESSION_TYPE": "filesystem"
          }

if 'CT_DOMAIN' in os.environ.keys():
    config['CT_DOMAIN'] = os.environ['CT_DOMAIN']
else:
    config['CT_DOMAIN'] = ''

if 'COMMUNI_SERVER' in os.environ.keys():
    app.config['COMMUNI_SERVER'] = os.environ['COMMUNI_SERVER']
else:
    app.config['COMMUNI_SERVER'] = ''

if 'VERSION' in os.environ.keys():
    config['VERSION'] = os.environ['VERSION']

app.config.update(config)
Session(app)


@app.route('/')
def index():
    return redirect('/main')


@app.before_request
def check_session():
    if request.endpoint != 'login':
        if 'ct_api' not in session:
            return redirect(url_for('login'))
        elif not session['ct_api'].who_am_i():
            return redirect(url_for('login'))


@app.route('/login_churchtools', methods=['GET', 'POST'])
def login():
    """
    Update login information for CT
    :return:
    """
    if request.method == 'POST':
        user = request.form['ct_user']
        password = request.form['ct_password']
        ct_domain = request.form['ct_domain']

        session['ct_api'] = CTAPI(
            ct_domain, ct_user=user, ct_password=password)
        if session['ct_api'].who_am_i() is not False:
            app.config['CT_DOMAIN'] = ct_domain
            return redirect('/main')

        error = 'Invalid Login'
        return render_template('login_churchtools.html',
                               error=error, ct_domain=app.config['CT_DOMAIN'])
    else:
        if 'ct_api' not in session:
            user = None
        else:
            user = session["ct_api"].who_am_i()
        return render_template('login_churchtools.html',
                               user=user, ct_domain=app.config['CT_DOMAIN'])


@app.route('/login_communi', methods=['GET', 'POST'])
def login_communi():
    """
    Update login information for Communi Login
    :return:
    """
    if request.method == 'POST':
        communi_server = request.form['communi_server']
        communi_token = request.form['communi_token']
        communi_appid = request.form['communi_appid']

        session['communi_api'] = CommuniApi(
            communi_server=communi_server,
            communi_token=communi_token,
            communi_appid=communi_appid)
        if session['communi_api'].who_am_i() is not False:
            app.config['COMMUNI_SERVER'] = communi_server
            return redirect('/main')

        error = 'Invalid Login'
        return render_template('login_communi.html',
                               error=error, communi_server=communi_server)
    else:
        if 'communi_api' not in session:
            user = None
        else:
            user = session["communi_api"].who_am_i()
        return render_template(
            'login_communi.html', user=user, communi_server=app.config['COMMUNI_SERVER'])


@app.route('/main')
def main():
    return render_template('main.html', version=app.config['VERSION'])


@app.route('/test')
def test():
    test = app.config['CT_DOMAIN'], app.config['COMMUNI_SERVER']
    return render_template('test.html', test=test)


@app.route('/communi/events')
def communi_events():
    """
    This page is used to admin communi groups based on churchtools planning information
    It will list all events from past 14 and future 15 days and show their link if they exist

    if event_id and action exist as GET param respective delete or update action will be executed
    """
    event_id = request.args.get('event_id')
    action = request.args.get('action')

    """
    #TODO unfinished code! #3
    delete_event_chats(ct_api, communi_api, event_ids)
    create_event_chats(ct_api, communi_api, event_ids, only_relevant=True)
    """

    reference_day = datetime.today()
    event_ids_past = get_x_day_event_ids(session['ct_api'], reference_day, -14)
    event_ids_future = get_x_day_event_ids(
        session['ct_api'], reference_day, 15)

    event_ids = event_ids_past + event_ids_future
    # TODO unfinished code! #3 - keep relevant only ...

    events = []
    for id in event_ids:
        event = session['ct_api'].get_events(eventId=id)[0]
        startdate = datetime.strptime(
            event['startDate'], '%Y-%m-%dT%H:%M:%S%z')
        datetext = startdate.astimezone().strftime('%a %b %d\t%H:%M')

        group_name = generate_group_name_for_event(session['ct_api'], id)
        group = session['communi_api'].getGroups(name=group_name)
        if len(group) == 0:
            group_id = None
        else:
            group_id = group['id']

        event_short = {
            "id": id,
            "date": datetext,
            "caption": event['name'],
            "group_id": group_id}
        events.append(event_short)

    test = {'event_id': event_id, "action": action, "other": None}

    if request.method == 'GET':
        return render_template('communi_events.html', events=events, test=test)

    elif request.method == 'POST':
        if 'event_id' not in request.form.keys():
            redirect('/communi/events')


@app.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'GET':
        session['serviceGroups'] = session['ct_api'].get_event_masterdata(
            type='serviceGroups', returnAsDict=True)

        events_temp = session['ct_api'].get_events()
        # events_temp.extend(session['ct_api'].get_events(eventId=2147))  # debugging
        # events_temp.extend(session['ct_api'].get_events(eventId=2129))  #
        # debugging
        logging.debug("{} Events loaded".format(len(events_temp)))

        event_choices = []
        session['event_agendas'] = {}
        session['events'] = {}

        for event in events_temp:
            agenda = session['ct_api'].get_event_agenda(event['id'])
            if agenda is not None:
                session['event_agendas'][event['id']] = agenda
                session['events'][event['id']] = event
                startdate = datetime.strptime(
                    event['startDate'], '%Y-%m-%dT%H:%M:%S%z')
                datetext = startdate.astimezone().strftime('%a %b %d\t%H:%M')
                event = {'id': event['id'],
                         'label': datetext + '\t' + event['name']}
                event_choices.append(event)

        logging.debug(
            "{} Events kept because schedule exists".format(len(events_temp)))

        return render_template('events.html', ct_domain=app.config['CT_DOMAIN'], event_choices=event_choices,
                               service_groups=session['serviceGroups'])
    elif request.method == 'POST':
        if 'event_id' not in request.form.keys():
            redirect('/events')
        event_id = int(request.form['event_id'])
        if 'submit_docx' in request.form.keys():
            event = session['events'][event_id]
            agenda = session['event_agendas'][event_id]

            selectedServiceGroups = \
                {key: value for key, value in session['serviceGroups'].items()
                 if 'service_group {}'.format(key) in request.form}

            document = session['ct_api'].get_event_agenda_docx(agenda, serviceGroups=selectedServiceGroups,
                                                               excludeBeforeEvent=False)
            filename = agenda['name'] + '.docx'
            document.save(filename)
            response = send_file(path_or_file=os.getcwd() +
                                 '/' + filename, as_attachment=True)
            os.remove(filename)
            return response

        elif 'submit_communi' in request.form.keys():
            error = 'Communi Group update not yet implemented'
        else:
            error = 'Requested function not detected in request'
        return render_template('main.html', error=error)
