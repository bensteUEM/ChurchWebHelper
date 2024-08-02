import ast
import base64
import io
import logging
import locale
import os
from datetime import datetime, time, timedelta
import re
from matplotlib import pyplot as plt
import pandas as pd

from flask import Flask, render_template, request, redirect, session, send_file, url_for

from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from communi_api.communi_api import CommuniApi
from communi_api.churchToolsActions import (
    delete_event_chats,
    create_event_chats,
    get_x_day_event_ids,
    generate_group_name_for_event,
)
from flask_session import Session
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.secret_key = os.urandom(16)

config = {"SESSION_PERMANENT": False, "SESSION_TYPE": "filesystem"}

if "CT_DOMAIN" in os.environ.keys():
    config["CT_DOMAIN"] = os.environ["CT_DOMAIN"]
else:
    config["CT_DOMAIN"] = ""

if "COMMUNI_SERVER" in os.environ.keys():
    app.config["COMMUNI_SERVER"] = os.environ["COMMUNI_SERVER"]
else:
    app.config["COMMUNI_SERVER"] = ""

if "VERSION" in os.environ.keys():
    config["VERSION"] = os.environ["VERSION"]

app.config.update(config)
locale.setlocale(locale.LC_TIME, "de_DE")

Session(app)


@app.route("/")
def index():
    return redirect("/main")


@app.before_request
def check_session():
    if request.endpoint != "login":
        if "ct_api" not in session:
            return redirect(url_for("login"))
        elif not session["ct_api"].who_am_i():
            return redirect(url_for("login"))


@app.route("/login_churchtools", methods=["GET", "POST"])
def login():
    """
    Update login information for CT
    :return:
    """
    if request.method == "POST":
        user = request.form["ct_user"]
        password = request.form["ct_password"]
        ct_domain = request.form["ct_domain"]

        session["ct_api"] = CTAPI(ct_domain, ct_user=user, ct_password=password)
        if session["ct_api"].who_am_i() is not False:
            app.config["CT_DOMAIN"] = ct_domain
            return redirect("/main")

        error = "Invalid Login"
        return render_template(
            "login_churchtools.html", error=error, ct_domain=app.config["CT_DOMAIN"]
        )
    else:
        if "ct_api" not in session:
            user = None
        else:
            user = session["ct_api"].who_am_i()
        return render_template(
            "login_churchtools.html", user=user, ct_domain=app.config["CT_DOMAIN"]
        )


@app.route("/login_communi", methods=["GET", "POST"])
def login_communi():
    """
    Update login information for Communi Login
    :return:
    """
    if request.method == "POST":
        communi_server = request.form["communi_server"]
        communi_token = request.form["communi_token"]
        communi_appid = request.form["communi_appid"]

        session["communi_api"] = CommuniApi(
            communi_server=communi_server,
            communi_token=communi_token,
            communi_appid=communi_appid,
        )
        if session["communi_api"].who_am_i() is not False:
            app.config["COMMUNI_SERVER"] = communi_server
            return redirect("/main")

        error = "Invalid Login"
        return render_template(
            "login_communi.html", error=error, communi_server=communi_server
        )
    else:
        if "communi_api" not in session:
            user = None
        else:
            user = session["communi_api"].who_am_i()
        return render_template(
            "login_communi.html", user=user, communi_server=app.config["COMMUNI_SERVER"]
        )


@app.route("/main")
def main():
    return render_template("main.html", version=app.config["VERSION"])


@app.route("/test")
def test():
    test = app.config["CT_DOMAIN"], app.config["COMMUNI_SERVER"]
    return render_template("test.html", test=test)


@app.route("/communi/events")
def communi_events():
    """
    This page is used to admin communi groups based on churchtools planning information
    It will list all events from past 14 and future 15 days and show their link if they exist

    if event_id and action exist as GET param respective delete or update action will be executed
    """
    event_id = request.args.get("event_id")
    action = request.args.get("action")

    if action == "update":
        create_event_chats(
            session["ct_api"], session["communi_api"], [event_id], only_relevant=False
        )
    elif action == "delete":
        delete_event_chats(session["ct_api"], session["communi_api"], [event_id])

    reference_day = datetime.today()
    event_ids_past = get_x_day_event_ids(session["ct_api"], reference_day, -7)
    event_ids_future = get_x_day_event_ids(session["ct_api"], reference_day, 15)

    event_ids = event_ids_past + event_ids_future
    # TODO unfinished code! #3 - keep relevant only ...

    events = []
    for id in event_ids:
        event = session["ct_api"].get_events(eventId=id)[0]
        startdate = datetime.strptime(event["startDate"], "%Y-%m-%dT%H:%M:%S%z")
        datetext = startdate.astimezone().strftime("%a %b %d\t%H:%M")

        group_name = generate_group_name_for_event(session["ct_api"], id)
        group = session["communi_api"].getGroups(name=group_name)
        if len(group) == 0:
            group_id = None
        else:
            group_id = group["id"]

        event_short = {
            "id": id,
            "date": datetext,
            "caption": event["name"],
            "group_id": group_id,
        }
        events.append(event_short)

    if request.method == "GET":
        return render_template("communi_events.html", events=events, test=None)

    elif request.method == "POST":
        if "event_id" not in request.form.keys():
            redirect("/communi/events")


@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "GET":
        session["serviceGroups"] = session["ct_api"].get_event_masterdata(
            type="serviceGroups", returnAsDict=True
        )

        events_temp = session["ct_api"].get_events()
        # events_temp.extend(session['ct_api'].get_events(eventId=2147))  # debugging
        # events_temp.extend(session['ct_api'].get_events(eventId=2129))  #
        # debugging
        logging.debug("{} Events loaded".format(len(events_temp)))

        event_choices = []
        session["event_agendas"] = {}
        session["events"] = {}

        for event in events_temp:
            agenda = session["ct_api"].get_event_agenda(event["id"])
            if agenda is not None:
                session["event_agendas"][event["id"]] = agenda
                session["events"][event["id"]] = event
                startdate = datetime.strptime(event["startDate"], "%Y-%m-%dT%H:%M:%S%z")
                datetext = startdate.astimezone().strftime("%a %b %d\t%H:%M")
                event = {"id": event["id"], "label": datetext + "\t" + event["name"]}
                event_choices.append(event)

        logging.debug("{} Events kept because schedule exists".format(len(events_temp)))

        return render_template(
            "events.html",
            ct_domain=app.config["CT_DOMAIN"],
            event_choices=event_choices,
            service_groups=session["serviceGroups"],
        )
    elif request.method == "POST":
        if "event_id" not in request.form.keys():
            redirect("/events")
        event_id = int(request.form["event_id"])
        if "submit_docx" in request.form.keys():
            event = session["events"][event_id]
            agenda = session["event_agendas"][event_id]

            selectedServiceGroups = {
                key: value
                for key, value in session["serviceGroups"].items()
                if "service_group {}".format(key) in request.form
            }

            document = session["ct_api"].get_event_agenda_docx(
                agenda, serviceGroups=selectedServiceGroups, excludeBeforeEvent=False
            )
            filename = agenda["name"] + ".docx"
            document.save(filename)
            response = send_file(
                path_or_file=os.getcwd() + "/" + filename, as_attachment=True
            )
            os.remove(filename)
            return response

        elif "submit_communi" in request.form.keys():
            error = "Communi Group update not yet implemented"
        else:
            error = "Requested function not detected in request"
        return render_template("main.html", error=error)


@app.route("/ct/calendar_appointments")
def ct_calendar_appointments():
    """
    page which can be used to display ChurchTools calendar appointments for IFrame use
    Use get param calendar_id=2 or similar to define a calendar
    Use get param days to specify the number of days
    Use optional get param services to specify a , separated list of service IDs to include
    use optional get param special_name to specify calendar id for special day names - using first event on that day multiple calendars can be specified using ,
    """
    calendar_id = request.args.get("calendar_id")
    days = request.args.get("days")
    if requested_services := request.args.get("services") is not None:
        requested_services = request.args.get("services").split(",")
        requested_services = [int(num) for num in requested_services]
    else:
        requested_services = None

    special_name_calendar_ids = request.args.get("special_name")
    if special_name_calendar_ids is not None:
        special_name_calendar_ids = request.args.get("special_name").split(",")
        special_name_calendar_ids = [int(num) for num in special_name_calendar_ids]

    if calendar_id is None or days is None:
        error = "please specify calendar_id and days as get param"
        return render_template("ct_calendar_appointments.html", error=error, data=None)

    calendar_ids = [int(calendar_id)]
    from_ = datetime.today()
    to_ = from_ + timedelta(days=int(days))

    appointments = session["ct_api"].get_calendar_appointments(
        calendar_ids=calendar_ids, from_=from_, to_=to_
    )

    # building a dict with day as key
    data = {}
    format_code = "%Y-%m-%dT%H:%M:%S%z"

    for appointment in appointments:
        caption = appointment["caption"]
        date = datetime.strptime(appointment["startDate"], format_code)

        day = date.astimezone().strftime("%A %e.%m.%Y")

        # Check if special name is requested with calendar IDs
        if isinstance(special_name_calendar_ids, list):
            special_names = session["ct_api"].get_calendar_appointments(
                calendar_ids=special_name_calendar_ids,
                from_=date,
                to_=date + timedelta(days=1),
            )
            if special_names is not None:
                if len(special_names) > 0:
                    special_name = special_names[0]["caption"]
                    day = f"{day} ({special_name})"

        time = date.astimezone().strftime("%H:%M")

        if requested_services is not None:
            event = session["ct_api"].get_event_by_calendar_appointment(
                appointment["id"], date
            )
            available_services = event["eventServices"]
            persons = [
                service["name"]
                for service in available_services
                if service["serviceId"] in requested_services
            ]
            persons = [person for person in persons if person is not None]
            if len(persons) > 0:
                persons = ", ".join(persons)
            else:
                persons = None
        else:
            persons = None

        if day not in data.keys():
            data[day] = []

        data[day].append({"time": time, "caption": caption, "persons": persons})

    return render_template("ct_calendar_appointments.html", data=data)


@app.route("/ct/service_workload", methods=["GET", "POST"])
def ct_service_workload():
    available_calendars = {
        cal["id"]: cal["name"] for cal in session["ct_api"].get_calendars()
    }

    if request.method == "GET":  # set defaults if case of new request
        DEFAULT_TIMEFRAME_MONTHS = 6
        from_date = datetime.combine(datetime.now().date(), time.min)
        to_date = datetime.combine(
            from_date + relativedelta(months=DEFAULT_TIMEFRAME_MONTHS), time.max
        )

        MIN_SERVICES_COUNT = 5

        EXCLUDE_PATTERNS = [
            ".*ohnzimmer.*",
            ".*chülergottesdienst.*",
            ".*aufnachmittag.*",
            ".*Trauung.*",
            ".*Andacht.*",
            ".*nzert.*",
            ".*chwesterherz.*",
        ]

        selected_calendars = available_calendars.keys()

    elif request.method == "POST":
        from_date = datetime.strptime(request.form["from_date"], "%Y-%m-%d")
        to_date = datetime.strptime(request.form["to_date"], "%Y-%m-%d")
        MIN_SERVICES_COUNT = int(request.form["min_services_count"])
        EXCLUDE_PATTERNS = (
            ast.literal_eval(request.form["exclude_patterns"])
            if len(request.form["exclude_patterns"]) > 0
            else []
        )

        selected_calendars = [
            int(calendar_id)
            for calendar_id in request.form.getlist("selected_calendars")
        ]

    # depend on system config!
    TECHNIK = 3
    relevant_service_category = [TECHNIK]

    # depend on system config!
    TON = 6
    FOLIEN_VORBEREITEN = 57
    STREAM = 69

    BEAM = 72
    TECH_SUPPORT = 104
    relevant_service_ids = [TON, BEAM, FOLIEN_VORBEREITEN, STREAM, TECH_SUPPORT]

    content = session["ct_api"].get_events(
        from_=from_date, to_=to_date, include="eventServices"
    )

    collected_data = []
    for event in content:
        if int(event["calendar"]["domainIdentifier"]) in selected_calendars:
            # filter to service categories only
            # filtered_services = [event["eventServices"] for event in content if content[0]["calendar"]["domainIdentifier"] in calendar_ids]

            # filter to specific services only
            for service in event["eventServices"]:
                exclude = False

                for pattern in EXCLUDE_PATTERNS:
                    if re.search(pattern, event["name"]):
                        exclude = True
                        break

                if exclude:
                    continue

                collected_data.append(
                    {
                        "Datum": datetime.strptime(
                            event["startDate"], "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "Eventname": event["name"],
                        "Dienst": service["serviceId"],
                        "Name": service["name"],
                    }
                )

    service_data = pd.DataFrame(collected_data)
    if len(service_data) == 0:
        service_data = pd.DataFrame(columns=["Datum", "Eventname", "Dienst", "Name"])

    # retrieve service names to replace numbers by labels
    services_map = session["ct_api"].get_event_masterdata(
        type="services", returnAsDict=True
    )

    # prepare mapping for requested service category and services only
    relevant_map = {}
    for id, item in services_map.items():
        if (
            item["serviceGroupId"] in relevant_service_category
            and item["id"] in relevant_service_ids
        ):
            relevant_map[id] = item["name"]

    # modify dataframe for readability
    service_data["Dienst"] = service_data["Dienst"].replace(relevant_map)
    filter_only_mapped = ~service_data["Dienst"].apply(lambda x: isinstance(x, int))

    # remove all items that are not mapped (not desired)
    service_data = service_data.loc[filter_only_mapped]
    services = set(service_data["Dienst"])

    # remove all entries which don't meet minimum service count required
    filter_names_keep = service_data["Name"].replace(
        service_data["Name"].value_counts() > MIN_SERVICES_COUNT
    )
    service_data = service_data.loc[filter_names_keep]

    # prepare event names
    event_names = dict(service_data["Eventname"].value_counts())

    # prepare names for display
    names = set(service_data["Name"])

    plots = []
    if len(service_data) > 0:
        # rolling chart
        df_rolling = (
            service_data.groupby("Name")["Datum"]
            .value_counts()
            .unstack()
            .fillna(0)
            .transpose()
        )
        df_rolling = df_rolling.rolling(window=len(df_rolling), min_periods=1).sum()

        ax1 = df_rolling.plot()
        y_min, y_max = ax1.get_ylim()
        ax1.set_yticks(range(int(y_min), int(y_max) + 1, 1))

        # Save it to a BytesIO object
        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        plots.append(base64.b64encode(img.getvalue()).decode("utf8"))

        # service types by person
        df_diensttyp = (
            service_data.groupby(["Dienst"])["Name"]
            .value_counts()
            .unstack()
            .fillna(0)
            .transpose()
        )
        df_diensttyp.plot.bar(stacked=True)

        # Save it to a BytesIO object
        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        plots.append(base64.b64encode(img.getvalue()).decode("utf8"))

    return render_template(
        "ct_service_workload.html",
        error=None,
        event_names=event_names,
        plots=plots,
        names=names,
        services=services,
        from_date=from_date,
        to_date=to_date,
        min_services_count=MIN_SERVICES_COUNT,
        exclude_patterns=EXCLUDE_PATTERNS,
        available_calendars=available_calendars,
        selected_calendars=selected_calendars,
    )
