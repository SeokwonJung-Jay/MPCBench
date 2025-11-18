"""Jira data generator module."""

from typing import Dict, Any, List
from datetime import datetime, timedelta


def generate_jira_data(world_state: Dict[str, Any], jira_plans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate Jira-like issues data from world_state and jira_plans.
    Must conform to schemas/jira_schema.json.
    """
    # Get projects from world_state
    projects = world_state.get("projects", [])
    issues = []
    
    # Build issue lookup by key
    issues_by_key = {}
    
    # Seed issues from projects
    for project in projects:
        project_key = project.get("project_key", "APP")
        jira_seeds = project.get("jira_seeds", [])
        
        for seed in jira_seeds:
            issue_key = seed.get("issue_key")
            issues_by_key[issue_key] = {
                "key": issue_key,
                "summary": seed.get("summary", ""),
                "status": seed.get("status", ""),
                "fixVersions": [],
                "project": {
                    "key": project_key
                }
            }
    
    # Process jira_plans
    for plan in jira_plans:
        kind = plan.get("kind")
        
        if kind == "update_issue_release":
            issue_key = plan.get("issue_key")
            release_target = plan.get("release_target")
            
            if issue_key in issues_by_key:
                # Add fixVersion with release date
                issues_by_key[issue_key]["fixVersions"] = [
                    {
                        "name": "v2.3.0",
                        "releaseDate": release_target
                    }
                ]
        
        elif kind == "issues_updated_last_week":
            # Mark issues as updated recently based on plan
            # The plan should specify which issues and when
            issue_keys = plan.get("issue_keys", [])
            updated_date = plan.get("updated_date")  # ISO datetime string from plan
            
            if not updated_date:
                # Fallback: use a generic recent date (not scenario-specific)
                base_date = datetime(2025, 11, 12)
                updated_date = (base_date - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+09:00")
            
            for issue_key in issue_keys:
                if issue_key in issues_by_key:
                    issues_by_key[issue_key]["updated"] = updated_date
    
    # Convert to list
    issues = list(issues_by_key.values())
    
    # Create projects list with fixVersions
    projects_list = []
    for project in projects:
        project_key = project.get("project_key", "APP")
        # Find fixVersions from issues in this project
        project_fix_versions = []
        for issue in issues:
            if issue.get("project", {}).get("key") == project_key:
                project_fix_versions.extend(issue.get("fixVersions", []))
        
        # Deduplicate fixVersions by name
        seen_versions = {}
        for fv in project_fix_versions:
            version_name = fv.get("name")
            if version_name and version_name not in seen_versions:
                seen_versions[version_name] = fv
        
        projects_list.append({
            "key": project_key,
            "name": project.get("name", ""),
            "fixVersions": list(seen_versions.values())
        })
    
    return {
        "projects": projects_list,
        "issues": issues
    }
