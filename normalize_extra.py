#!/usr/bin/env python3
"""Per-source normalizers for the 7 new state schemas (CO CT NJ PA WA WI NE)."""
import re


def _i(v):
    if v is None:
        return None
    m = re.search(r"-?\d+", str(v))
    return int(m.group()) if m else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _c(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def norm_co(r):
    caps = {
        "infant": _i(r.get("licensed_infant_capacity")),
        "toddler": _i(r.get("licensed_toddler_capacity")),
        "preschool": _i(r.get("licensed_nyo_capacity")),
        "school_age": _i(r.get("licensed_school_age_capacity")),
        "total": _i(r.get("total_licensed_capacity")),
    }
    if caps["total"] is None:
        parts = [v for k, v in caps.items() if k != "total" and v is not None]
        caps["total"] = sum(parts) if parts else None
    return {
        "source": "CO-CDHS", "provider_id": _c(r.get("provider_id")) or "",
        "name": _c(r.get("provider_name")),
        "type": _c(r.get("provider_service_type")),
        "status": "LICENSED",
        "address": _c(r.get("address_line_1")),
        "city": _c(r.get("city")), "county": _c(r.get("county")),
        "state": "CO", "zip": _c(r.get("zip")), "phone": _c(r.get("phone")),
        "capacity_total": caps["total"],
        "capacity_infant": caps["infant"], "capacity_toddler": caps["toddler"],
        "capacity_preschool": caps["preschool"],
        "capacity_school_age": caps["school_age"],
        "ages_served": None, "lat": None, "lon": None,
    }


def norm_ct(r):
    reg = _i(r.get("regularcapacity")) or 0
    sa = _i(r.get("schoolagecapacity")) or 0
    return {
        "source": "CT-OEC",
        "provider_id": _c(r.get("licensenumber")) or _c(r.get("credentialidnt")) or "",
        "name": _c(r.get("name")),
        "type": _c(r.get("licensetype")),
        "status": _c(r.get("status")),
        "address": _c(r.get("address1")),
        "city": _c(r.get("city")), "county": None,
        "state": "CT", "zip": _c(r.get("zip")), "phone": None,
        "capacity_total": (reg + sa) if (reg or sa) else None,
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": sa if sa else None,
        "ages_served": None, "lat": None, "lon": None,
    }


def norm_nj(r):
    return {
        "source": "NJ-DCF", "provider_id": _c(r.get("center")) or "",
        "name": _c(r.get("center")),
        "type": None,
        "status": None,
        "address": _c(r.get("addr1")),
        "city": _c(r.get("city")), "county": _c(r.get("county")),
        "state": "NJ", "zip": _c(r.get("zip")), "phone": _c(r.get("phone")),
        "capacity_total": _i(r.get("capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": _c(r.get("ages")), "lat": None, "lon": None,
    }


def norm_pa(r):
    return {
        "source": "PA-OCDEL",
        "provider_id": _c(r.get("master_provider_index")) or _c(r.get("mpi_id")) or "",
        "name": _c(r.get("facility_name")),
        "type": _c(r.get("provider_type")),
        "status": None,
        "address": _c(r.get("facility_address")),
        "city": _c(r.get("facility_city")), "county": _c(r.get("facility_county")),
        "state": "PA", "zip": _c(r.get("facility_zip_code")),
        "phone": _c(r.get("facility_phone")),
        "capacity_total": _i(r.get("capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": None, "lat": None, "lon": None,
    }


def norm_wa(r):
    return {
        "source": "WA-DCYF",
        "provider_id": _c(r.get("famlinkid")) or _c(r.get("sspsprovidernumber")) or "",
        "name": _c(r.get("providername")) or _c(r.get("doingbusinessas")),
        "type": _c(r.get("facilitytypegeneric")),
        "status": _c(r.get("latestoperatingstatus")),
        "address": _c(r.get("physicalstreetaddress")),
        "city": _c(r.get("physicalcity")), "county": _c(r.get("physicalcounty")),
        "state": "WA", "zip": _c(r.get("physicalzip")),
        "phone": _c(r.get("primarycontactphonenumber")),
        "capacity_total": _i(r.get("licensecapacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": (_c(r.get("startingage")) and
                        (str(r.get("startingage")) + " to " + str(r.get("endingage")))),
        "lat": _f(r.get("physciallatitude")), "lon": _f(r.get("physicallongitude")),
    }


def norm_wi(r):
    return {
        "source": "WI-DCF", "provider_id": _c(r.get("FacilityNumber")) or "",
        "name": _c(r.get("FacilityName")),
        "type": _c(r.get("CategoryType")),
        "status": "LICENSED",
        "address": _c(r.get("LocationLineAddress1")),
        "city": _c(r.get("City")), "county": None,
        "state": "WI", "zip": _c(r.get("ZipCode")),
        "phone": _c(r.get("LocationPrimaryPhoneNumber")),
        "capacity_total": _i(r.get("Capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": (_c(r.get("FromAge")) and
                        (str(r.get("FromAge")) + " to " + str(r.get("ToAge")))),
        "lat": _f(r.get("Latitude")), "lon": _f(r.get("Longitude")),
    }


def norm_ne(r):
    return {
        "source": "NE-DHHS",
        "provider_id": _c(r.get("License_Number")) or str(r.get("OBJECTID") or ""),
        "name": _c(r.get("Full_Name")),
        "type": _c(r.get("License_Type")),
        "status": _c(r.get("GIS_Status")),
        "address": _c(r.get("Address")),
        "city": _c(r.get("City")), "county": _c(r.get("County")),
        "state": "NE", "zip": _c(r.get("Zip_Code1")), "phone": _c(r.get("Phone")),
        "capacity_total": _i(r.get("Capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": (_c(r.get("Ages_From")) and
                        (str(r.get("Ages_From")) + " to " + str(r.get("Ages_To")))),
        "lat": None, "lon": None,
    }




def norm_ma(r):
    st = _c(r.get("licensed_provider_status"))
    active = st in (None, "Current", "Renewal in progress")
    return {
        "source": "MA-EEC", "provider_id": _c(r.get("provider_number")) or "",
        "name": _c(r.get("program_name")),
        "type": _c(r.get("program_type")),
        "status": st or "UNKNOWN",
        "address": _c(r.get("program_street_address1")),
        "city": _c(r.get("program_city")), "county": None,
        "state": "MA", "zip": _c(r.get("program_zipcode")),
        "phone": _c(r.get("program_phone")),
        "capacity_total": _i(r.get("licensed_capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": "Early Head Start" if r.get("early_head_start") == "Y" else None,
        "lat": _f(r.get("program_latitude")), "lon": _f(r.get("program_longitude")),
        "_active": active,
    }


def norm_vt(r):
    return {
        "source": "VT-DHCD", "provider_id": _c(r.get("provider_id")) or "",
        "name": _c(r.get("provider_name")),
        "type": _c(r.get("license_type")),
        "status": "LICENSED",
        "address": _c(r.get("address_1")),
        "city": _c(r.get("town")) or _c(r.get("provider_town")),
        "county": _c(r.get("county")),
        "state": "VT", "zip": _c(r.get("zip")),
        "phone": _c(r.get("phone_number")),
        "capacity_total": _i(r.get("total_licensed_capacity")),
        "capacity_infant": _i(r.get("infant_licensed_capacity")),
        "capacity_toddler": _i(r.get("toddler_licensed_capacity")),
        "capacity_preschool": _i(r.get("preschool_licensed_capacity")),
        "capacity_school_age": _i(r.get("school_age_licensed_capacity")),
        "ages_served": None,
        "lat": _f(r.get("latitude")), "lon": _f(r.get("longitude")),
        "_vacancies_total": _i(r.get("total_reported_vacancies")) if r.get("total_reported_vacancies") is not None else (
            sum(v for v in [_i(r.get("reported_infant_vacancies")), _i(r.get("reported_toddler_vacancies")),
                            _i(r.get("reported_preschool_vacancies")), _i(r.get("reported_school_age_vacancies"))] if v) or None),
    }


def norm_mn(r):
    return {
        "source": "MN-DHS", "provider_id": str(r.get("providerid") or ""),
        "name": _c(r.get("do_bus_as")) or _c(r.get("providername")) or str(r.get("providerid")),
        "type": _c(r.get("typeofcare")) or _c(r.get("tocfinal")),
        "status": _c(r.get("licnsetype")) or "LICENSED",
        "address": _c(r.get("address")),
        "city": _c(r.get("city")), "county": _c(r.get("county")),
        "state": "MN", "zip": _c(r.get("zip")),
        "phone": _c(r.get("phone")) if r.get("phone") else None,
        "capacity_total": _i(r.get("licnsecap")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": None, "lat": None, "lon": None,
        "_vacancies_total": _i(r.get("truevacs")),
    }


def norm_ok(r):
    return {
        "source": "OK-DHS", "provider_id": _c(r.get("Case_Number")) or "",
        "name": _c(r.get("Facility_Name")),
        "type": _c(r.get("Facility_Type")),
        "status": "LICENSED",
        "address": _c(r.get("Location")),
        "city": None, "county": _c(r.get("County_of_Facility")),
        "state": "OK", "zip": None,
        "phone": _c(r.get("Facility_Phone")),
        "capacity_total": _i(r.get("Capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": _c(r.get("Ages_Accepted")),
        "lat": None, "lon": None,
    }


def norm_va(r):
    return {
        "source": "VA-DSS (CCAA layers)", "provider_id": "",
        "name": _c(r.get("Business_Name")),
        "type": _c(r.get("ProviderType")) or _c(r.get("ProgramType")),
        "status": "LICENSED",
        "address": _c(r.get("Address")),
        "city": _c(r.get("City")), "county": _c(r.get("County")),
        "state": "VA", "zip": _c(r.get("Zip")),
        "phone": None,
        "capacity_total": _i(r.get("Capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": None,
        "lat": _f(r.get("Latitude")), "lon": _f(r.get("Longitude")),
        "_layer": _c(r.get("LicenseType")),
    }




def norm_hi(r):
    AREA2COUNTY = {"AB": "Hawaii", "AC": "Kauai", "AD": "Maui", "AE": "Maui", "AF": "Maui", "AG": "Honolulu"}
    svc = r.get("service", {})
    det = r.get("detail") or {}
    summ = det.get("summary", {})
    dtl = det.get("details", {})
    loc = dtl.get("locationAddress") or {}
    TYPE = {"OR": "In-Home Provider", "CG": "Group Home/Center", "DH": "In-Home Provider (DH)"}
    lic = summ.get("licensed")
    status = "LICENSED" if lic else "UNLICENSED"
    return {
        "source": "HI-DHS (BrowsAPI)", "provider_id": str(svc.get("serviceId") or ""),
        "name": _c(summ.get("serviceName")) or _c(svc.get("serviceName")),
        "type": TYPE.get(summ.get("providerType"), _c(summ.get("providerType"))),
        "status": status,
        "address": _c(loc.get("street1")),
        "city": _c(loc.get("city")), "county": AREA2COUNTY.get(str(svc.get("area", ""))[:2]),
        "state": "HI", "zip": str(loc.get("zipCode") or "") or None,
        "phone": None,
        "capacity_total": _i(summ.get("capacity")),
        "capacity_infant": None, "capacity_toddler": None,
        "capacity_preschool": None, "capacity_school_age": None,
        "ages_served": (
            f"{summ.get('minAgeValue', '')} {summ.get('minAgeUnit', '')} - {summ.get('maxAgeValue', '')} {summ.get('maxAgeUnit', '')}"
            if summ.get("minAgeValue") is not None else None),
        "lat": None, "lon": None,
    }


NORMALIZERS = {
    "co": norm_co, "ct": norm_ct, "nj": norm_nj, "pa": norm_pa,
    "wa": norm_wa, "wi": norm_wi, "ne": norm_ne,
    "ma": norm_ma, "vt": norm_vt, "mn": norm_mn, "ok": norm_ok,
    "va": norm_va, "hi": norm_hi,
}
