"""Contacts data generator module."""

from typing import Dict, Any, List


def generate_contacts_data(world_state: Dict[str, Any], contacts_plans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a contacts store from world_state and contacts_plans.
    Must conform to schemas/contacts_schema.json.
    """
    scenario_id = world_state.get("scenario_id", "scenario_A")
    plans_count = len(contacts_plans)
    print(f"[contacts_generator] Start: scenario_id={scenario_id}, plans={plans_count}")
    
    # Build person lookup by ID
    people_by_id = {person["id"]: person for person in world_state["people"]}
    
    # Start with all people from world_state
    contacts_set = set()
    contacts = []
    
    # Add all people as contacts
    for person in world_state["people"]:
        person_id = person["id"]
        if person_id not in contacts_set:
            contacts.append({
                "id": person_id,
                "name": person["name"],
                "email": person["email"]
            })
            contacts_set.add(person_id)
    
    # Process plans to ensure specific participants are included
    for plan in contacts_plans:
        kind = plan.get("kind")
        if kind == "ensure_contacts_exist":
            participants = plan.get("participants", [])
            for person_id in participants:
                if person_id not in contacts_set:
                    person = people_by_id.get(person_id)
                    if person:
                        contacts.append({
                            "id": person_id,
                            "name": person["name"],
                            "email": person["email"]
                        })
                        contacts_set.add(person_id)
    
    contacts_count = len(contacts)
    print(f"[contacts_generator] Result: contacts={contacts_count}")
    
    return {
        "contacts": contacts
    }
