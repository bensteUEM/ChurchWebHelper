"""This module is used for reuseable functions which are used to transform service assignment information."""

import logging
from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from datetime import datetime, time

logger = logging.getLogger(__name__)


def get_title_name_services(
    calendar_ids: list[int],
    appointment_id: int,
    relevant_date: datetime,
    api: CTAPI,
    considered_program_services: list[int],
    considered_groups: list[int],
) -> str:
    """Helper function which retrieves a text representation of a service including the persons title based on considered groups.

    1. Lookup relevant services
    2. Lookup the prefix of the person to be used based on group assignemnts

    Args:
        calendar_ids: list of calendars to consider
        appointment_id: number of the calendar appointment
        relevant_date: the date of the event to be unique
        api: reference to api in order to request more information from CT
        considered_program_services: list of services which should be considered
        considered_groups: groups which should be used as prefix if applicable

    Returns:
        formatted useable string with title and name
    """
    relevant_event = api.get_event_by_calendar_appointment(
        appointment_id=appointment_id, start_date=relevant_date
    )

    relevant_persons = []
    for service_id in considered_program_services:
        relevant_persons.extend(
            api.get_persons_with_service(
                eventId=relevant_event["id"], serviceId=service_id
            )
        )

    names_with_title = []
    for person in relevant_persons:
        title_prefix = get_group_title_of_person(
            person_id=person["personId"], relevant_groups=considered_groups, api=api
        )
        if person["personId"]:
            lastname = person["person"]["domainAttributes"]["lastName"]
            formatted_name = f"{title_prefix} {lastname}".lstrip()
        else:
            formatted_name = "Noch unbekannt"
        names_with_title.append(formatted_name)

    return ", ".join(names_with_title)


def get_group_title_of_person(
    person_id: int, relevant_groups: list[int], api: CTAPI
) -> str:
    """Retrieve name of first group for specified person and gender if possible.

    Args:
        person_id: CT id of the user
        relevant_groups: the CT id of any groups to be considered as title
        ct_api: access to request more info from CT

    Permissions:
        view person
        view alldata (Persons)
        view group

    Returns:
        Prefix which is used as title incl. gendered version
    """
    for group_id in relevant_groups:
        group_member_ids = [
            group["personId"] for group in api.get_group_members(group_id=group_id)
        ]
        if person_id in group_member_ids:
            group_name = api.get_groups(group_id=group_id)[0]["name"]
            break
    else:
        group_name = ""

    # add 'IN' suffix to first part of group member in order to apply german gender for most common cases
    person = api.get_persons(ids=[person_id])[0]

    gender_map = api.get_persons_masterdata(resultClass="sexes", returnAsDict=True)

    if gender_map[person["sexId"]] == "sex.female" and len(group_name) > 0:
        parts = group_name.split(" ")
        part1_gendered = parts[0] + "in"
        group_name = " ".join([part1_gendered] + parts[1:])

    return group_name


def get_group_name_services(
    calendar_ids: list[int],
    appointment_id: int,
    relevant_date: datetime,
    api: CTAPI,
    considered_music_services: list[int],
    considered_grouptype_role_ids: list[int],
) -> str:
    """Helper which will retrieve the name of special services involved with the calendar appointment on that day.

    1. get event
    2. for each service
        - check who is assigned
        - check what groups are relevant
    3. for each person in service
        - check group membership
        - add groupname to result list if applicable
    4. join the groups applicable to a useable text string

    Args:
        calendar_ids: list of calendars to consider
        appointment_id: number of the calendar appointment
        relevant_date: the date of the event to be unique
        api: reference to api in order to request more information from CT
        considered_music_services: list of services which should be considered
        considered_grouptype_role_ids: list of grouptype_id roles to be considered (differs by group type!)

    Returns:
        text which can be used as suffix - empty in case no special service
    """
    relevant_event = api.get_event_by_calendar_appointment(
        appointment_id=appointment_id, start_date=relevant_date
    )

    result_groups = []
    for service in considered_music_services:
        service_assignments = api.get_persons_with_service(
            eventId=relevant_event["id"], serviceId=service
        )
        persons = [service["person"] for service in service_assignments]
        relevant_group_results = [
            service["groupIds"]
            for service in api.get_event_masterdata()["services"]
            if service["id"] in considered_music_services
        ]
        considered_group_ids = {
            int(group_id)
            for group_result in relevant_group_results
            for group_id in group_result
        }
        for person in persons:
            group_assignemnts = api.get_groups_members(
                group_ids=considered_group_ids,
                grouptype_role_ids=considered_grouptype_role_ids,
                person_ids=[int(person["domainIdentifier"])],
            )
            relevant_group_ids = [group["groupId"] for group in group_assignemnts]
            for group_id in relevant_group_ids:
                group = api.get_groups(group_id=group_id)[0]
                result_groups.append(group["name"])
    return "mit " + " und ".join(result_groups) if len(result_groups) > 0 else ""


def get_service_assignment_lastnames_or_unknown(
    ct_api: CTAPI, service_name: str, event_id: int, config: dict
) -> str:
    """Helper which retrieves a list of service assignments and converts them to printable format.

    Arguments:
        ct_api: access to a connected instance of CT API in order to retrive more data
        service_name: name of the service to retrieve
        event_id: number for which is the source of all assignments
        config: defaults dict which is used to determine specific group allocations
    Returns:
        a formatted string with lastnames.
        In case a person was not assigned ? is used.
        In case a text is used instead of a user the full text is used
    """
    service_assignments_names = []
    result = ""
    for service_id in config.get(f"{service_name}_service_ids", []):
        for service_assignment in ct_api.get_persons_with_service(
            eventId=event_id, serviceId=service_id
        ):
            if service_assignment.get("personId"):
                service_assignments_names.append(
                    service_assignment["person"]["domainAttributes"]["lastName"]
                )
            elif service_assignment.get("name"):
                service_assignments_names.append(
                    service_assignment["name"]
                )
            else:
                service_assignments_names.append("?")

    result = ", ".join(set(service_assignments_names))
    logger.debug("finished preparing predigt_lastname attributes")
    return result


def replace_special_services_with_service_shortnames(special_services: str) -> str:
    """Helper which replaces long "special service" strings by their shortform.

    Args:
        special_services: original special service detected
        e.g. "mit Posaunenchor" or "mit Posaunenchor und Kirchenchor"

    Returns:
        short version of special services without mit and separated by , only
    """
    special_services = special_services.split(" und ")
    short_services = []

    for special_service in special_services:
        match special_service.removeprefix("mit "):
            case "Posaunenchor":
                short_services.append("Pos.Chor")
            case "InJoy Chor":
                short_services.append("InJ.Chor")
            case "Kirchenchor":
                short_services.append("Kir.Chor")
            case _:
                short_services.append(special_service.removeprefix("mit "))
                logger.warning("no known shortservice version of %s", special_service)
    return ", ".join(short_services)
