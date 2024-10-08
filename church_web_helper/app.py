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
import urllib

import toml

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
else:
    with open("pyproject.toml", "r") as f:
        pyproject_data = toml.load(f)
    config["VERSION"] = pyproject_data["tool"]["poetry"]["version"]

app.config.update(config)
locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")

Session(app)


@app.route("/")
def index():
    return redirect("/main")


@app.before_request
def check_session():
    """Session variable should contain ct_api and communi_api.
    If not a redirect to respective login pages should be executed
    """
    if request.endpoint != "login_ct" and request.endpoint != "login_communi": 
        #Check CT Login
        if not session.get("ct_api"):
            return redirect(url_for("login_ct"))
        elif not session["ct_api"].who_am_i():
            return redirect(url_for("login_ct"))
        #Check Communi Login
        if not session.get("communi_api"):
            return redirect(url_for("login_communi"))
        elif not session["communi_api"].who_am_i():
            return redirect(url_for("login_communi"))

@app.route("/ct/login", methods=["GET", "POST"])
def login_ct():
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


@app.route("/communi/login", methods=["GET", "POST"])
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
    # default params if not specified
    DEFAULT_CALENDAR_ID = 2
    DEFAULT_DAYS = 14
    DEFAULT_SERVICE_ID = [1]
    DEFAULT_HIDE_MENU = False

    calendar_id = request.args.get("calendar_id")
    days = request.args.get("days")
    if "hide_menu" in request.args:
        hide_menu = ast.literal_eval(request.args.get("hide_menu"))

    if services := request.args.get("services"):
        services = request.args.get("services").split(",")
        services = [int(num) for num in services]

    if special_name_calendar_ids := request.args.get("special_names"):
        special_name_calendar_ids = request.args.get("special_names").split(",")
        special_name_calendar_ids = [int(num) for num in special_name_calendar_ids]
    else:
        special_name_calendar_ids = []

    if not calendar_id or not days or not services:  # set a default
        calendar_id = DEFAULT_CALENDAR_ID
        days = DEFAULT_DAYS
        services = DEFAULT_SERVICE_ID
        hide_menu = DEFAULT_HIDE_MENU

    calendar_appointments_params = urllib.parse.urlencode(
        {
            "calendar_id": calendar_id,
            "days": days,
            "hide_menu": hide_menu,
        }
    )
    calendar_appointments_params += "&services=" + ",".join(
        [str(service) for service in services]
    )
    calendar_appointments_params += "&special_names=" + ",".join(
        [
            str(special_name_calendar_id)
            for special_name_calendar_id in special_name_calendar_ids
        ]
    )

    calendar_ids = [int(calendar_id)]
    from_ = datetime.today()
    to_ = from_ + timedelta(days=int(days))

    appointments = session["ct_api"].get_calendar_appointments(
        calendar_ids=calendar_ids, from_=from_, to_=to_
    )

    # building a dict with day as key
    data = {}
    format_code = "%Y-%m-%dT%H:%M:%S%z"

    if not appointments:
        error = "please specify different calendar_id and days as get param"
        return render_template(
            "ct_calendar_appointments.html",
            error=error,
            data=None,
            calendar_appointments_default_params=calendar_appointments_params,
        )

    for appointment in appointments:
        caption = appointment["caption"]
        date = datetime.strptime(appointment["startDate"], format_code)

        day = date.astimezone().strftime("%A %e.%m.%Y")

        # Check if special name is requested with calendar IDs
        if (
            isinstance(special_name_calendar_ids, list)
            and len(special_name_calendar_ids) > 0
        ):
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

        if services is not None:
            event = session["ct_api"].get_event_by_calendar_appointment(
                appointment["id"], date
            )
            available_services = event["eventServices"]
            persons = [
                service["name"]
                for service in available_services
                if service["serviceId"] in services
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

    return render_template(
        "ct_calendar_appointments.html",
        data=data,
        calendar_appointments_params=calendar_appointments_params,
        hide_menu=hide_menu,
    )


@app.route("/ct/service_workload", methods=["GET", "POST"])
def ct_service_workload():
    available_calendars = {
        cal["id"]: cal["name"] for cal in session["ct_api"].get_calendars()
    }

    available_service_categories = {
        serviceGroup["id"]: serviceGroup["name"]
        for serviceGroup in session["ct_api"].get_event_masterdata(type="serviceGroups")
    }
    available_service_types_by_category = {
        key: [] for key in available_service_categories
    }
    for service in session["ct_api"].get_event_masterdata(type="services"):
        available_service_types_by_category[service["serviceGroupId"]].append(
            {"id": service["id"], "name": service["name"]}
        )

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

        selected_service_types = {}

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
        selected_service_types = [
            int(service_type_id)
            for service_type_id in request.form.getlist("selected_service_types")
        ]

    collected_data = []
    for event in session["ct_api"].get_events(
        from_=from_date, to_=to_date, include="eventServices"
    ):
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
                        "Monat": datetime.strptime(
                            event["startDate"], "%Y-%m-%dT%H:%M:%SZ"
                        ).strftime("%B"),
                        "Eventname": event["name"],
                        "Dienst": service["serviceId"],
                        "Name": service["name"],
                    }
                )

    service_data = pd.DataFrame(collected_data)

    # fallback in case of no data filtered
    if len(service_data) == 0:
        service_data = pd.DataFrame(columns=["Datum", "Eventname", "Dienst", "Name"])

    # prepare mapping for requested service category and services only
    relevant_map = {}
    for servicegroup_id, service_types in available_service_types_by_category.items():
        for service_type in service_types:
            if service_type["id"] in selected_service_types:
                relevant_map[service_type["id"]] = service_type["name"]

    # modify dataframe for readability
    service_data["Dienst"] = service_data["Dienst"].replace(relevant_map)
    filter_only_mapped = ~service_data["Dienst"].apply(lambda x: isinstance(x, int))
    service_data["Name"] = service_data["Name"].fillna("? noch offen")

    # remove all items that are not mapped (not desired)
    service_data = service_data.loc[filter_only_mapped]
    # remove all entries which don't meet minimum service count required
    filter_names_keep = service_data["Name"].replace(
        service_data["Name"].value_counts() > MIN_SERVICES_COUNT
    )
    service_data = service_data.loc[filter_names_keep]

    # create list of available names based on filter criteria
    available_persons = list(service_data["Name"].unique())
    if request.method == "GET":  # set defaults if case of new request
        selected_persons = available_persons
    elif request.method == "POST":
        selected_persons = (
            request.form.getlist("selected_persons")
            if len(request.form.getlist("selected_persons")) > 0
            else available_persons
        )

    service_data = service_data[service_data["Name"].isin(selected_persons)]

    # prepare event names
    event_names = dict(service_data["Eventname"].value_counts())

    # create plots
    plots = {}
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
        plots["Kummulierter Verlauf je Person"] = base64.b64encode(
            img.getvalue()
        ).decode("utf8")

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
        plots["Diensttypen je Person im Gesamtzeitraum"] = base64.b64encode(
            img.getvalue()
        ).decode("utf8")

    # create tables
    tables = {}
    if len(service_data) > 0:
        # prepare tables
        df_table_1 = (
            service_data.groupby("Name")["Monat"]
            .value_counts()
            .unstack()
            .fillna(0)
            .transpose()
            .sort_index(ascending=False)
        )
        df_table_2 = (
            df_table_1.rolling(window=len(df_table_1), min_periods=1)
            .sum()
            .astype(int)
            .sort_index(ascending=False)
        )
        tables = {
            "Monatsübersicht": df_table_1.to_html(
                classes="table table-striped text-center", index=True
            ),
            "Kummulierte Monatsansicht": df_table_2.to_html(
                classes="table table-striped text-center", index=True
            ),
        }

    return render_template(
        "ct_service_workload.html",
        error=None,
        event_names=event_names,
        plots=plots,
        tables=tables,
        from_date=from_date,
        to_date=to_date,
        min_services_count=MIN_SERVICES_COUNT,
        exclude_patterns=EXCLUDE_PATTERNS,
        available_calendars=available_calendars,
        selected_calendars=selected_calendars,
        available_service_categories=available_service_categories,
        available_service_types_by_category=available_service_types_by_category,
        selected_service_types=selected_service_types,
        available_persons=available_persons,
        selected_persons=selected_persons,
    )
