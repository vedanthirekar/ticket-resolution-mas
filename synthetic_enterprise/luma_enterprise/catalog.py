from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocationSpec:
    reference: str
    name: str
    timezone: str
    hours: tuple[tuple[int, int, int], ...]

    @property
    def open_weekdays(self) -> tuple[int, ...]:
        return tuple(weekday for weekday, _, _ in self.hours)

    def hours_for(self, weekday: int) -> tuple[int, int] | None:
        return next(
            (
                (opens_hour, closes_hour)
                for day, opens_hour, closes_hour in self.hours
                if day == weekday
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class EmployeeSpec:
    reference: str
    name: str
    location_reference: str
    role: str
    qualifications: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    reference: str
    name: str
    category: str
    duration_minutes: int
    price_cents: int
    credit_cost: int | None
    qualification: str
    allowed_locations: tuple[str, ...]
    is_add_on: bool = False
    resource_type: str | None = None


LOCATIONS = (
    LocationSpec(
        "LOC-IND",
        "Indianapolis",
        "America/Indiana/Indianapolis",
        ((0, 8, 20), (1, 8, 20), (2, 8, 20), (3, 8, 20), (4, 8, 18), (5, 9, 16)),
    ),
    LocationSpec(
        "LOC-CHI",
        "Chicago",
        "America/Chicago",
        ((0, 7, 20), (1, 7, 20), (2, 7, 20), (3, 7, 20), (4, 7, 20), (5, 9, 17), (6, 9, 17)),
    ),
    LocationSpec(
        "LOC-DEN",
        "Denver",
        "America/Denver",
        ((1, 9, 19), (2, 9, 19), (3, 9, 19), (4, 9, 19), (5, 9, 16), (6, 9, 16)),
    ),
)


EMPLOYEES = (
    EmployeeSpec("EMP-001", "Maya Chen", "LOC-IND", "location_lead", ()),
    EmployeeSpec(
        "EMP-002",
        "Elena Ruiz",
        "LOC-IND",
        "massage_therapist",
        ("massage-core", "massage-advanced"),
    ),
    EmployeeSpec(
        "EMP-003", "Jordan Brooks", "LOC-IND", "esthetician", ("facial-core", "facial-advanced")
    ),
    EmployeeSpec(
        "EMP-004", "Priya Shah", "LOC-IND", "recovery_specialist", ("recovery", "consultation")
    ),
    EmployeeSpec(
        "EMP-005", "Noah Williams", "LOC-IND", "massage_therapist", ("massage-core", "prenatal")
    ),
    EmployeeSpec("EMP-006", "Olivia Martin", "LOC-CHI", "location_lead", ("consultation",)),
    EmployeeSpec(
        "EMP-007",
        "Marcus Lee",
        "LOC-CHI",
        "massage_therapist",
        ("massage-core", "massage-advanced", "sports"),
    ),
    EmployeeSpec(
        "EMP-008", "Sofia Patel", "LOC-CHI", "esthetician", ("facial-core", "facial-advanced")
    ),
    EmployeeSpec(
        "EMP-009", "Grace Kim", "LOC-CHI", "recovery_specialist", ("recovery", "consultation")
    ),
    EmployeeSpec(
        "EMP-010", "Daniel Ortiz", "LOC-CHI", "massage_therapist", ("massage-core", "prenatal")
    ),
    EmployeeSpec("EMP-011", "Avery Johnson", "LOC-DEN", "location_lead", ("consultation",)),
    EmployeeSpec(
        "EMP-012", "Riley Morgan", "LOC-DEN", "massage_therapist", ("massage-core", "sports")
    ),
    EmployeeSpec("EMP-013", "Layla Hassan", "LOC-DEN", "esthetician", ("facial-core",)),
    EmployeeSpec(
        "EMP-014",
        "Ethan Nguyen",
        "LOC-DEN",
        "recovery_specialist",
        ("recovery", "consultation", "altitude-recovery"),
    ),
    EmployeeSpec(
        "EMP-015",
        "Chloe Davis",
        "LOC-DEN",
        "massage_therapist",
        ("massage-core", "massage-advanced", "prenatal"),
    ),
)


ALL_LOCATIONS = tuple(location.reference for location in LOCATIONS)
IND_CHI = ("LOC-IND", "LOC-CHI")

SERVICES = (
    ServiceSpec(
        "SVC-001", "Swedish Massage 50", "massage", 50, 12000, 1, "massage-core", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-002", "Swedish Massage 80", "massage", 80, 17500, 2, "massage-core", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-003", "Deep Tissue 50", "massage", 50, 14500, 1, "massage-advanced", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-004", "Deep Tissue 80", "massage", 80, 20500, 2, "massage-advanced", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-005", "Sports Recovery Massage", "massage", 60, 16000, 1, "sports", ALL_LOCATIONS
    ),
    ServiceSpec("SVC-006", "Prenatal Massage", "massage", 60, 15000, 1, "prenatal", ALL_LOCATIONS),
    ServiceSpec(
        "SVC-007", "Hot Stone Massage", "massage", 80, 21500, 2, "massage-advanced", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-008",
        "Essential Facial",
        "facial",
        50,
        12500,
        1,
        "facial-core",
        ALL_LOCATIONS,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-009",
        "Hydration Facial",
        "facial",
        60,
        15500,
        1,
        "facial-core",
        ALL_LOCATIONS,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-010",
        "Brightening Facial",
        "facial",
        60,
        16500,
        1,
        "facial-core",
        ALL_LOCATIONS,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-011",
        "Advanced Renewal Facial",
        "facial",
        75,
        21000,
        2,
        "facial-advanced",
        IND_CHI,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-012",
        "Clarifying Facial",
        "facial",
        50,
        14000,
        1,
        "facial-core",
        ALL_LOCATIONS,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-013",
        "Advanced Peel",
        "facial",
        45,
        19000,
        2,
        "facial-advanced",
        IND_CHI,
        resource_type="facial_room",
    ),
    ServiceSpec(
        "SVC-014",
        "Compression Recovery",
        "recovery",
        30,
        5500,
        None,
        "recovery",
        ALL_LOCATIONS,
        resource_type="recovery_station",
    ),
    ServiceSpec(
        "SVC-015", "Assisted Stretch", "recovery", 30, 7000, None, "recovery", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-016", "Assisted Stretch Extended", "recovery", 50, 10500, 1, "recovery", ALL_LOCATIONS
    ),
    ServiceSpec(
        "SVC-017",
        "Recovery Circuit",
        "recovery",
        45,
        9500,
        1,
        "recovery",
        ALL_LOCATIONS,
        resource_type="recovery_station",
    ),
    ServiceSpec(
        "SVC-018",
        "Altitude Recovery Session",
        "recovery",
        45,
        11000,
        1,
        "altitude-recovery",
        ("LOC-DEN",),
        resource_type="recovery_station",
    ),
    ServiceSpec(
        "SVC-019",
        "Wellness Consultation",
        "consultation",
        30,
        5000,
        None,
        "consultation",
        ALL_LOCATIONS,
    ),
    ServiceSpec(
        "SVC-020",
        "Recovery Plan Consultation",
        "consultation",
        45,
        7500,
        None,
        "consultation",
        ALL_LOCATIONS,
    ),
    ServiceSpec(
        "SVC-021",
        "Aromatherapy Add-on",
        "add_on",
        0,
        2000,
        None,
        "massage-core",
        ALL_LOCATIONS,
        True,
    ),
    ServiceSpec(
        "SVC-022",
        "Scalp Treatment Add-on",
        "add_on",
        15,
        3000,
        None,
        "massage-core",
        ALL_LOCATIONS,
        True,
    ),
    ServiceSpec(
        "SVC-023",
        "Eye Treatment Add-on",
        "add_on",
        15,
        3500,
        None,
        "facial-core",
        ALL_LOCATIONS,
        True,
    ),
    ServiceSpec(
        "SVC-024",
        "LED Treatment Add-on",
        "add_on",
        20,
        4500,
        None,
        "facial-core",
        ALL_LOCATIONS,
        True,
    ),
    ServiceSpec(
        "SVC-025",
        "Percussion Therapy Add-on",
        "add_on",
        15,
        3000,
        None,
        "recovery",
        ALL_LOCATIONS,
        True,
    ),
)
