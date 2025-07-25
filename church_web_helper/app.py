"""Flask main app."""

import ast
import base64
import io
import json
import locale
import logging
import logging.config
import os
import re
import urllib
from datetime import datetime, time
from pathlib import Path

import pandas as pd
import pytz
import toml
import vobject
from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from communi_api.churchToolsActions import (
    create_event_chats,
    delete_event_chats,
    generate_group_name_for_event,
    get_x_day_event_ids,
)
from communi_api.communi_api import CommuniApi
from dateutil.relativedelta import relativedelta
from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from matplotlib import pyplot as plt

from church_web_helper.export_docx import get_plan_months_docx
from church_web_helper.export_xlsx import get_plan_months_xlsx
from church_web_helper.helper import (
    deduplicate_df_index_with_lists,
    extract_relevant_calendar_appointment_shortname,
    get_primary_resource,
    get_special_day_name,
)
from church_web_helper.service_information_transformation import (
    get_group_name_services,
    get_service_assignment_lastnames_or_unknown,
    get_title_name_services,
    replace_special_services_with_service_shortnames,
)
from flask_session import Session

config_file = Path("logging_config.json")
with config_file.open(encoding="utf-8") as f_in:
    logging_config = json.load(f_in)
    log_directory = Path(logging_config["handlers"]["file"]["filename"]).parent
    if not log_directory.exists():
        log_directory.mkdir(parents=True)
    logging.config.dictConfig(config=logging_config)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(16)

config = {"SESSION_PERMANENT": False, "SESSION_TYPE": "filesystem"}

config["CT_DOMAIN"] = os.environ.get("CT_DOMAIN", "")

app.config["COMMUNI_SERVER"] = os.environ.get("COMMUNI_SERVER", "")

if "VERSION" in os.environ:
    config["VERSION"] = os.environ["VERSION"]
else:
    with open("pyproject.toml") as f:
        pyproject_data = toml.load(f)
    config["VERSION"] = pyproject_data["tool"]["poetry"]["version"]

app.config.update(config)
locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")

Session(app)


@app.route("/")
def index():
    return redirect("/main")


@app.before_request
def check_session() -> Response | None:
    """Session variable should contain ct_api and communi_api.

    If not a redirect to respective login pages should be executed
    """
    if request.endpoint not in ("login_ct", "login_communi"):
        # Check CT Login
        if not session.get("ct_api") or not session["ct_api"].who_am_i():
            return redirect(url_for("login_ct"))
        # Check Communi Login
        if not session.get("communi_api") or not session["communi_api"].who_am_i():
            return redirect(url_for("login_communi"))
        return None
    return None


@app.route("/ct/login", methods=["GET", "POST"])
def login_ct() -> str:
    """Update login information for CT."""
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
    user = None if "ct_api" not in session else session["ct_api"].who_am_i()
    return render_template(
        "login_churchtools.html", user=user, ct_domain=app.config["CT_DOMAIN"]
    )


@app.route("/communi/login", methods=["GET", "POST"])
def login_communi() -> str:
    """Update login information for Communi Login."""
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
    user = None if "communi_api" not in session else session["communi_api"].who_am_i()
    return render_template(
        "login_communi.html", user=user, communi_server=app.config["COMMUNI_SERVER"]
    )


@app.route("/main")
def main() -> str:
    return render_template("main.html", version=app.config["VERSION"])


@app.route("/test")
def test() -> str:
    test = app.config["CT_DOMAIN"], app.config["COMMUNI_SERVER"]
    return render_template("test.html", message=test)


@app.route("/communi/events")
def communi_events() -> Response | str:
    """This page is used to admin communi groups based on churchtools planning information.

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
    event_ids_future = get_x_day_event_ids(session["ct_api"], reference_day, 25)

    event_ids = event_ids_past + event_ids_future
    # TODO unfinished code! #3 - keep relevant only ...

    events = []
    for id in event_ids:
        event = session["ct_api"].get_events(eventId=id)[0]
        startdate = datetime.strptime(event["startDate"], "%Y-%m-%dT%H:%M:%S%z")
        datetext = startdate.astimezone().strftime("%a %b %d\t%H:%M")

        group_name = generate_group_name_for_event(session["ct_api"], id)
        group = session["communi_api"].getGroups(name=group_name)
        group_id = None if len(group) == 0 else group["id"]

        event_short = {
            "id": id,
            "date": datetext,
            "caption": event["name"],
            "group_id": group_id,
        }
        events.append(event_short)

    if request.method == "GET":
        return render_template("communi_events.html", events=events, test=None)

    if request.method == "POST" and "event_id" not in request.form:
        redirect("/communi/events")
        return None
    return None


@app.route("/download/events", methods=["GET", "POST"])
def download_events() -> str:
    if request.method == "GET":
        session["serviceGroups"] = session["ct_api"].get_event_masterdata(
            resultClass="serviceGroups", returnAsDict=True
        )

        events_temp = session["ct_api"].get_events()
        # events_temp.extend(session['ct_api'].get_events(eventId=2147))  # debugging
        # events_temp.extend(session['ct_api'].get_events(eventId=2129))  #
        # debugging
        logger.debug(f"{len(events_temp)} Events loaded")

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

        logger.debug(f"{len(events_temp)} Events kept because schedule exists")

        return render_template(
            "download_events.html",
            ct_domain=app.config["CT_DOMAIN"],
            event_choices=event_choices,
            service_groups=session["serviceGroups"],
        )
    if request.method == "POST":
        if "event_id" not in request.form:
            return redirect(url_for("download_events"))
        event_id = int(request.form["event_id"])
        if "submit_docx" in request.form:
            event = session["events"][event_id]
            agenda = session["event_agendas"][event_id]

            selectedServiceGroups = {
                key: value
                for key, value in session["serviceGroups"].items()
                if f"service_group {key}" in request.form
            }

            document = session["ct_api"].get_event_agenda_docx(
                # TODO@bensteUEM: https://github.com/bensteUEM/ChurchWebHelper/issues/47 .
                agenda,
                serviceGroups=selectedServiceGroups,
                excludeBeforeEvent=False,
            )
            filename = agenda["name"] + ".docx"
            document.save(filename)
            response = send_file(
                path_or_file=os.getcwd() + "/" + filename, as_attachment=True
            )
            os.remove(filename)
            return response

        if "submit_communi" in request.form:
            error = "Communi Group update not yet implemented"
        else:
            error = "Requested function not detected in request"
        return render_template("main.html", error=error)
    return None


@app.route("/download/plan_months", methods=["GET", "POST"])
def download_plan_months() -> str:
    # default params are set ELKW1610.krz.tools specific and must be adjusted in case a different CT instance is used
    DEFAULTS = {
        "default_timeframe_months": 1,
        "special_day_calendar_ids": [52, 72],
        "selected_calendars": [2],
        "available_resource_type_ids": [4, 6, 5],
        "selected_resources": [-1, 8, 20, 21, 16, 17],
        "selected_program_services": [1],
        "selected_title_prefix_groups": [89, 355, 358, 361, 367, 370, 373],
        "selected_music_services": [9, 61],
        "grouptype_role_id_leads": [
            9,  # Leitung in "Dienst"
            16,  # Leitung in "Kleingruppe"
        ],
        "program_service_group_id": 1,
        "music_service_group_ids": [4],
        "predigt_service_ids": [1],
        "organist_service_ids": [2, 87],
        "musikteam_service_ids": [10],
        "taufe_service_ids": [127],
        "abendmahl_service_ids": [100],
    }
    logger.debug("defaults defined")

    available_calendars = {
        cal["id"]: cal["name"] for cal in session["ct_api"].get_calendars()
    }
    logger.debug("retrieved available calendars len=%s", len(available_calendars))
    resources = session["ct_api"].get_resource_masterdata(resultClass="resources")
    logger.debug("retrieved available resources len=%s", len(resources))

    # resource_types = session["ct_api"].get_resource_masterdata(result_type="resourceTypes") # Check your Resource Types IDs here for customization
    available_resources = {
        -1: "Ortsangabe nicht ausgewählt",
        **{
            resource["id"]: resource["name"]
            for resource in resources
            if resource["resourceTypeId"] in DEFAULTS.get("available_resource_type_ids")
        },
    }
    logger.debug(
        "selected available resources %s/%s", len(available_resources), len(resources)
    )

    event_masterdata = session["ct_api"].get_event_masterdata()
    # service_groups = event_masterdata["serviceGroups"] # Check your Service Group IDs here for customization
    available_program_services = {
        service["id"]: service["name"]
        for service in event_masterdata["services"]
        if service["serviceGroupId"] == DEFAULTS.get("program_service_group_id")
    }
    logger.debug(
        "retrieved available program services len=%s", len(available_program_services)
    )

    available_music_services = {
        service["id"]: service["name"]
        for service in event_masterdata["services"]
        if service["serviceGroupId"] in DEFAULTS.get("music_service_group_ids")
    }
    logger.debug(
        "retrieved available music services len=%s", len(available_music_services)
    )

    if request.method == "GET":
        logger.info("Responding to GET request")
        selected_calendars = DEFAULTS.get(
            "selected_calendars", available_calendars.keys()
        )
        selected_resources = DEFAULTS.get(
            "selected_resources", available_resources.keys()
        )
        selected_program_services = DEFAULTS.get(
            "selected_program_services", available_program_services.keys()
        )
        selected_music_services = DEFAULTS.get(
            "selected_music_services", available_music_services.keys()
        )
        logger.debug(
            "identified selected calendars (%s/%s) resources (%s/%s) program_services (%s/%s) music_services (%s/%s)",
            len(selected_calendars),
            len(available_calendars),
            len(selected_resources),
            len(available_resources),
            len(selected_program_services),
            len(available_program_services),
            len(selected_music_services),
            len(available_music_services),
        )

        from_date = datetime.now().date()
        if from_date.month == 12:
            from_date = datetime(from_date.year + 1, 1, 1)
        else:
            from_date = datetime(from_date.year, from_date.month + 1, 1)
        from_date = datetime.combine(from_date, time.min)

        to_date = datetime.combine(
            from_date
            + relativedelta(months=DEFAULTS.get("default_timeframe_months"))
            - relativedelta(days=1),
            time.max,
        )
        logger.debug("defined time range %s - %s", from_date, to_date)

        return render_template(
            "download_plan_months.html",
            data=None,
            available_calendars=available_calendars,
            selected_calendars=selected_calendars,
            available_resources=available_resources,
            selected_resources=selected_resources,
            available_program_services=available_program_services,
            selected_program_services=selected_program_services,
            available_music_services=available_music_services,
            selected_music_services=selected_music_services,
            from_date=from_date,
            to_date=to_date,
        )
    if request.method == "POST":
        logger.info("Responding to POST request")
        from_date = datetime.strptime(request.form["from_date"], "%Y-%m-%d")
        to_date = datetime.strptime(request.form["to_date"], "%Y-%m-%d")

        selected_calendars = [
            int(calendar_id)
            for calendar_id in request.form.getlist("selected_calendars")
        ]
        selected_resources = [
            int(resource_id)
            for resource_id in request.form.getlist("selected_resources")
        ]

        selected_program_services = [
            int(service_id)
            for service_id in request.form.getlist("selected_program_services")
        ]

        selected_music_services = [
            int(service_id)
            for service_id in request.form.getlist("selected_music_services")
        ]
        logger.debug(
            "identified selected calendars (%s/%s) resources (%s/%s) program_services (%s/%s) music_services (%s/%s)",
            len(selected_calendars),
            len(available_calendars),
            len(selected_resources),
            len(available_resources),
            len(selected_program_services),
            len(available_program_services),
            len(selected_music_services),
            len(available_music_services),
        )

        from_date = datetime.strptime(request.form["from_date"], "%Y-%m-%d")
        to_date = datetime.strptime(request.form["to_date"], "%Y-%m-%d")
        logger.debug("defined time range %s - %s", from_date, to_date)

        calendar_appointments = session["ct_api"].get_calendar_appointments(
            calendar_ids=selected_calendars, from_=from_date, to_=to_date
        )

        entries = []
        for counter, item in enumerate(calendar_appointments):
            logger.debug(
                "Iterating calendar appointments %s/%s",
                counter + 1,
                len(calendar_appointments),
            )
            # startDate casting
            if len(item["startDate"]) > 10:
                item["startDate"] = (
                    datetime.strptime(item["startDate"], "%Y-%m-%dT%H:%M:%Sz")
                    .replace(tzinfo=pytz.UTC)
                    .astimezone()
                )
            elif len(item["startDate"]) == 10:
                item["startDate"] = datetime.strptime(
                    item["startDate"], "%Y-%m-%d"
                ).astimezone()
            logger.debug("converted start date as %s", item["startDate"])

            event = session["ct_api"].get_event_by_calendar_appointment(
                appointment_id=item["id"], start_date=item["startDate"]
            )

            # Simple attributes
            data = {
                "caption": item["caption"],
                "startDate": item["startDate"],
                "shortName": extract_relevant_calendar_appointment_shortname(
                    item["caption"] + (item["subtitle"] if item["subtitle"] else "")
                ),
                "shortDay": item["startDate"].strftime("%a %d.%m"),
                "specialDayName": get_special_day_name(
                    ct_api=session["ct_api"],
                    special_name_calendar_ids=DEFAULTS.get("special_day_calendar_ids"),
                    date=item["startDate"],
                ),
                "shortTime": item["startDate"].strftime("%H.%S")
                if item["startDate"].hour > 0
                else "Ganztag",
            }
            logger.debug("finished preparing simple attributes")

            # Predigt
            data["predigt"] = get_title_name_services(
                calendar_ids=selected_calendars,
                appointment_id=item["id"],
                relevant_date=item["startDate"],
                api=session["ct_api"],
                considered_program_services=selected_program_services,
                considered_groups=DEFAULTS.get("selected_title_prefix_groups"),
            )
            logger.debug("finished preparing predigt attributes")

            # Special Service - usually high-level indication of music
            data["specialService"] = get_group_name_services(
                calendar_ids=selected_calendars,
                appointment_id=item["id"],
                relevant_date=item["startDate"],
                api=session["ct_api"],
                considered_music_services=selected_music_services,
                considered_grouptype_role_ids=DEFAULTS.get("grouptype_role_id_leads"),
            )
            logger.debug("finished preparing specialService attributes")

            # location
            data["location"] = list(
                get_primary_resource(
                    appointment_id=item["id"],
                    relevant_date=item["startDate"],
                    ct_api=session["ct_api"],
                    considered_resource_ids=selected_resources,
                )
            )
            if len(data["location"]) > 0:
                data["location"] = data["location"][0]
            else:
                data["location"] = "Ortsangabe nicht ausgewählt"
                if -1 not in selected_resources:
                    # -1 is a special case added to available resources manually
                    continue  # don't add calendar appointment to entries

            replacements = {
                "Marienkirche": "Marienkirche Baiersbronn",
                "Michaelskirche (MIKI)": "Michaelskirche Friedrichstal",
                "Johanneskirche (JOKI)": "Johanneskirche Tonbach",
                "Gemeindehaus Großer Saal": "Gemeindehaus Baiersbronn",
                "Gemeindehaus Kleiner Saal": "Gemeindehaus Baiersbronn",
            }

            for old, new in replacements.items():
                data["location"] = data["location"].replace(old, new)
            logger.debug("finished preparing location attributes")

            # Individual services with lastnames for Table overview
            for service_name in ["predigt", "organist", "musikteam", "taufe"]:
                data[f"{service_name}_lastname"] = (
                    get_service_assignment_lastnames_or_unknown(
                        ct_api=session["ct_api"],
                        service_name=service_name,
                        event_id=event["id"],
                        config=DEFAULTS,
                    )
                )

            # musik service is combination of lastnames and specialService groupname
            special_services_short = []
            if len(data["specialService"]) > 0:
                special_services_short = (
                    replace_special_services_with_service_shortnames(
                        special_services=data["specialService"]
                    )
                )

            combined_music = [data["musikteam_lastname"], special_services_short]
            data["musik"] = ", ".join(item for item in combined_music if len(item) > 0)
            logger.debug("finished preparing musik attributes")

            # Taufe should have a "Taufe" prefix or no value at all
            data["taufe"] = (
                "Taufe " + data["taufe_lastname"]
                if len(data["taufe_lastname"]) > 0
                else ""
            )
            logger.debug("finished preparing taufe attributes")

            # Abendmahl detecte by service assignments
            abendmahl = []
            for service_id in DEFAULTS.get("abendmahl_service_ids", []):
                abendmahl.extend(
                    session["ct_api"].get_persons_with_service(
                        eventId=event["id"], serviceId=service_id
                    )
                )
            data["abendmahl"] = "Abendmahl" if len(abendmahl) > 0 else ""
            logger.debug("finished preparing abendmahl attributes")

            entries.append(data)

        df_raw: pd.DataFrame = pd.DataFrame(entries)
        df_data_pivot = (
            df_raw.pivot_table(
                values=[
                    "shortTime",
                    "shortName",
                    "predigt",
                    "specialService",
                    "taufe",
                    "abendmahl",
                    "musik",
                    "predigt_lastname",
                    "organist_lastname",
                ],
                index=["startDate", "shortDay", "specialDayName"],
                columns=["location"],
                aggfunc=list,
                fill_value="",
            )
            .reorder_levels([1, 0], axis=1)
            .sort_index(axis=1)
            .reset_index()
            .drop(columns="startDate")
        )
        logger.debug("created dataframe")
        df_data = deduplicate_df_index_with_lists(df_data_pivot)

        logger.debug("starting to process action")
        action = request.form.get("action")
        if action == "Auswahl anpassen":
            logger.debug("change selected params only")
            return render_template(
                "download_plan_months.html",
                data=df_data.to_html(
                    classes="table table-striped text-center", index=True
                ),
                available_calendars=available_calendars,
                selected_calendars=selected_calendars,
                available_resources=available_resources,
                selected_resources=selected_resources,
                available_program_services=available_program_services,
                selected_program_services=selected_program_services,
                available_music_services=available_music_services,
                selected_music_services=selected_music_services,
                from_date=from_date,
                to_date=to_date,
            )

        if action == "DOCx Document Download":
            logger.debug("Preparing Download as DOCx")
            document = get_plan_months_docx(df_data, from_date=from_date)
            filename = f"Monatsplan_{from_date.strftime('%Y_%B')}.docx"
            document.save(filename)
            response = send_file(
                path_or_file=os.getcwd() + "/" + filename, as_attachment=True
            )
            os.remove(filename)
            return response

        if action == "Excel Download":
            logger.debug("Preparing Download as Excel")
            filename = f"Monatsplan_{from_date.strftime('%Y_%B')}.xlsx"
            workbook = get_plan_months_xlsx(
                df_data, from_date=from_date, filename=filename
            )
            workbook.close()
            response = send_file(
                path_or_file=os.getcwd() + "/" + filename, as_attachment=True
            )
            os.remove(filename)
            return response
    return None


@app.route("/ct/calendar_appointments")
def ct_calendar_appointments() -> str:
    """Page which can be used to display ChurchTools calendar appointments for IFrame use.

    Use get param calendar_id=2 or similar to define a calendar
    Use get param days to specify the number of days
    Use optional get param services to specify a , separated list of service IDs to include
    use optional get param special_name to specify calendar id for special day names - using first event on that day multiple calendars can be specified using
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
    to_ = from_ + relativedelta(days=int(days))

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
            special_name = get_special_day_name(
                ct_api=session["ct_api"],
                special_name_calendar_ids=special_name_calendar_ids,
                date=date,
            )
            session["ct_api"].get_calendar_appointments(
                calendar_ids=special_name_calendar_ids,
                from_=date,
                to_=date + relativedelta(days=1),
            )
            if special_name is not None and len(special_name) > 0:
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
            persons = ", ".join(persons) if len(persons) > 0 else None
        else:
            persons = None

        if day not in data:
            data[day] = []

        data[day].append({"time": time, "caption": caption, "persons": persons})

    return render_template(
        "ct_calendar_appointments.html",
        data=data,
        calendar_appointments_params=calendar_appointments_params,
        hide_menu=hide_menu,
    )


@app.route("/ct/service_workload", methods=["GET", "POST"])
def ct_service_workload() -> str:
    available_calendars = {
        cal["id"]: cal["name"] for cal in session["ct_api"].get_calendars()
    }

    available_service_categories = {
        serviceGroup["id"]: serviceGroup["name"]
        for serviceGroup in session["ct_api"].get_event_masterdata(
            resultClass="serviceGroups"
        )
    }
    available_service_types_by_category = {
        key: [] for key in available_service_categories
    }
    for service in session["ct_api"].get_event_masterdata(resultClass="services"):
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
                        ).strftime("%m %B"),
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
    for service_types in available_service_types_by_category.values():
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
            .sort_index(ascending=True)
        )
        df_table_2 = (
            df_table_1.rolling(window=len(df_table_1), min_periods=1)
            .sum()
            .astype(int)
            .sort_index(ascending=True)
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


@app.route("/ct/contacts", methods=["GET"])
def ct_contacts() -> str:
    """Vcard export for ChurchTools contacts.

    Generates VCards for Name / Phone number for all available persons
    """
    if request.args.get("download"):
        persons = session["ct_api"].get_persons()
        vcards = []
        for person in persons:
            vcard = vobject.vCard()

            # Add a full name
            vcard.add("fn")
            vcard.fn.value = f"{person['firstName']} {person['lastName']}"

            # Add a HOME phone number
            home_tel = vcard.add("tel")
            home_tel.value = person.get("phonePrivate")
            home_tel.type_param = "HOME"

            # Add a WORK phone number
            work_tel = vcard.add("tel")
            work_tel.value = person.get("phoneWork")
            work_tel.type_param = "WORK"

            # Add a CELL phone number
            cell_tel = vcard.add("tel")
            cell_tel.value = person.get("mobile")
            cell_tel.type_param = "CELL"

            vcards.append(vcard)

        # Create an in-memory bytes buffer
        output = io.BytesIO()

        # Write each vCard to the buffer
        for vcard in vcards:
            output.write(vcard.serialize().encode("utf-8"))

        # Set the file pointer to the beginning of the buffer
        output.seek(0)

        # Send the file as a download
        return send_file(
            output,
            as_attachment=True,
            download_name="ct_contacts.vcf",
            mimetype="text/vcard",
        )

    return render_template("ct_contacts.html")


@app.route(
    "/ct/posts",
    methods=["GET", "POST"],
)
def ct_posts() -> str:
    """Posts to Communi from ChurchTools Beiträge.

    Used to assist with reposting entries from ChurchTools to Communi.
    use DEFAULT_GROUP_ID to pre-select your most frequently used group
    """
    posts = session.get("ct_api").get_posts()
    available_groups = {
        group["id"]: group["title"] for group in session["communi_api"].getGroups()
    }

    DEFAULT_GROUP_ID = 65021  # noqa: N806

    if request.method == "GET":  # set defaults if case of new request
        selected_group = DEFAULT_GROUP_ID

    elif request.method == "POST" and (
        (selected_group := request.form.get("selected_group", type=int))
        and (post_id := request.form.get("repost_post_id", type=int))
    ):
        posts = [post for post in posts if post["id"] == post_id]
        post = posts[0]

        GROUP_ID = selected_group
        base_url = re.match(
            r"^(https?:\/\/[^/]+)(?:.*)", post.get("group").get("apiUrl")
        ).group(1)

        session["communi_api"].recommendation(
            group_id=GROUP_ID,
            title=f"{post.get('title')} ({post['group']['title']})",
            description=post.get("content"),
            post_date=datetime.strptime(
                post.get("publishedDate"), "%Y-%m-%dT%H:%M:%SZ"
            ).astimezone(),
            pic_url=post.get("images")[0] if len(post.get("images")) > 0 else "",
            link=f"{base_url}/posts/{post.get('id')}",
            is_official=True,
        )

        return render_template(
            "ct_posts.html",
            posts=posts,
            available_groups=available_groups,
            selected_group=selected_group,
            message=f"Reposted {post.get('title')} to Communi",
        )

    return render_template(
        "ct_posts.html",
        posts=posts,
        message=None,
        available_groups=available_groups,
        selected_group=selected_group,
    )
