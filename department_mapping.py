"""
Department ID to Department Name and Area Mapping
Maps department_id to Vietnamese department names and their areas
"""

DEPARTMENT_MAPPING = {
    "68c7d0345ae9e9e13020dbb8": {
        "name": "Kiểm soát an ninh",
        "area": "KHU VỰC KSAN"
    },
    "690583e4d2739e469f4efba4": {
        "name": "Buồng giam 01",
        "area": "KHU VỰC BUỒNG GIAM"
    },
    "68c7c559e6824a87950bc084": {
        "name": "Buồng giam 02",
        "area": "KHU VỰC BUỒNG GIAM"
    },
    "68c7be7b1d4a863510d396ee": {
        "name": "Hàng rào 01",
        "area": "KHU VỰC HÀNG RÀO"
    },
    "68c7c5b5b24a5bb09d737226": {
        "name": "Hàng rào 02",
        "area": "KHU VỰC HÀNG RÀO"
    },
    "68c7c0605ae9e9e13020db7c": {
        "name": "Cổng trại 01",
        "area": "KHU VỰC CỔNG TRẠI"
    },
    "68c7bf4f3387f32b37ff83ac": {
        "name": "Cổng trại 02",
        "area": "KHU VỰC CỔNG TRẠI"
    },
    "69143609a0dd9986d5defb20": {
        "name": "Lao động",
        "area": "KHU VỰC LAO ĐỘNG"
    },
    "6913075f8387ea258f4c9671": {
        "name": "Ra vào 01",
        "area": "KHU VỰC KIỂM SOÁT RA VÀO"
    },
    "691307314d6dcb1f5b061537": {
        "name": "Ra vào 02",
        "area": "KHU VỰC KIỂM SOÁT RA VÀO"
    },
}


def get_department_name(department_id: str) -> str:
    """
    Get department name by department_id
    
    Args:
        department_id: The department ID to look up
    
    Returns:
        Department name if found, otherwise returns the department_id
    """
    dept_info = DEPARTMENT_MAPPING.get(department_id)
    if dept_info:
        return dept_info.get("name", department_id)
    return department_id


def get_department_area(department_id: str) -> str:
    """
    Get department area by department_id
    
    Args:
        department_id: The department ID to look up
    
    Returns:
        Department area if found, otherwise returns empty string
    """
    dept_info = DEPARTMENT_MAPPING.get(department_id)
    if dept_info:
        return dept_info.get("area", "")
    return ""


def get_department_info(department_id: str) -> dict:
    """
    Get full department information (name and area) by department_id
    
    Args:
        department_id: The department ID to look up
    
    Returns:
        Dictionary with 'name' and 'area' keys, or empty dict if not found
    """
    return DEPARTMENT_MAPPING.get(department_id, {})


def get_all_departments() -> dict:
    """
    Get all department mappings
    
    Returns:
        Dictionary of all department_id to department_info mappings
    """
    return DEPARTMENT_MAPPING.copy()

