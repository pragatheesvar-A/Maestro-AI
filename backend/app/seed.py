"""
Deterministic demo-data seed script.

Generates:
  - 3 login users (admin / manager / employee demo accounts)
  - 18 skills with realistic transferability relationships (skill graph)
  - 30 employees with varied skills, workload, availability, location
  - 100 tasks across multiple projects with varied priority/SLA/complexity
  - An initial optimized allocation (runs the real OR-Tools solver once)

Guarantees required for the reliable disruption demo:
  - Employee "Priya" always exists (id printed at the end)
  - Task "T4021" always exists, titled to match the spec's example, and is
    assigned to Priya by the initial optimization pass whenever the solver
    finds her a feasible (and typically best) candidate for it.

Run: python -m app.seed
"""
import random
from datetime import datetime, timedelta

from app.database import Base, engine, SessionLocal
from app.models import (
    User, RoleEnum, Skill, Employee, EmployeeSkill, EmployeePreference,
    Task, TaskRequirement, TaskPriority, TaskStatus, AvailabilityStatus, TaskHistory, gen_id,
)
from app.auth import hash_password
from app.services.skills import embed_text, build_skill_graph
from app.optimizer.engine import run_allocation
from app.config import get_settings

settings = get_settings()

SKILLS = [
    "Python", "JavaScript", "TypeScript", "React", "Vue", "Node.js",
    "FastAPI", "Django", "SQL", "PostgreSQL", "AWS", "Docker", "Kubernetes",
    "Machine Learning", "Data Analysis", "UI Design", "UX Design",
    "Project Management", "Agile", "Java", "Spring Boot",
]

LOCATIONS = ["Bengaluru", "Chennai", "Hyderabad", "Remote", "Pune"]
PROJECTS = ["Aurora Platform", "Nimbus Mobile", "Atlas Data", "Vertex Infra", "Helix Analytics"]
FIRST_NAMES = [
    "Priya", "Karthik", "Arun", "Divya", "Ravi", "Sneha", "Vikram", "Anita",
    "Rahul", "Meera", "Suresh", "Kavya", "Arjun", "Pooja", "Manoj", "Deepa",
    "Sanjay", "Lakshmi", "Vijay", "Nisha", "Rohit", "Swathi", "Kiran", "Anjali",
    "Naveen", "Preethi", "Ashok", "Divya2", "Harish", "Tanvi",
]
ROLES = ["Software Engineer", "Frontend Engineer", "Backend Engineer", "Data Scientist",
         "DevOps Engineer", "UI/UX Designer", "QA Engineer", "Project Manager"]

TASK_VERBS = ["Implement", "Design", "Fix", "Optimize", "Migrate", "Build", "Refactor", "Integrate", "Test", "Deploy"]
TASK_SUBJECTS = [
    "user authentication flow", "payment gateway integration", "dashboard analytics widget",
    "mobile onboarding screen", "API rate limiter", "data pipeline for reporting",
    "search relevance ranking", "notification service", "CI/CD pipeline", "database schema migration",
    "React component library", "Kubernetes autoscaling policy", "ML model for churn prediction",
    "customer support chatbot", "UI redesign for settings page", "load testing suite",
    "third-party billing API", "caching layer for API", "role-based access control", "audit logging system",
]


def get_or_create_skill(db, name):
    skill = db.query(Skill).filter(Skill.name == name).first()
    if not skill:
        skill = Skill(name=name, category="technical")
        skill.set_embedding(embed_text(name))
        db.add(skill)
        db.flush()
    return skill


def seed():
    # Reset the RNG on every call (not just at module import) so the demo
    # dataset -- and critically, the T4021 -> Priya initial assignment -- is
    # bit-for-bit reproducible every time this is re-run, including via the
    # live "Reset Demo" button during a presentation.
    random.seed(settings.RANDOM_SEED)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("[seed] Creating skills...")
    skill_objs = {name: get_or_create_skill(db, name) for name in SKILLS}
    db.commit()
    build_skill_graph(list(skill_objs.keys()))

    print("[seed] Creating users...")
    db.add(User(email="admin@smartalloc.ai", hashed_password=hash_password("admin123"),
                full_name="Ananya Admin", role=RoleEnum.ADMIN))
    db.add(User(email="manager@smartalloc.ai", hashed_password=hash_password("manager123"),
                full_name="Manoj Manager", role=RoleEnum.MANAGER))
    db.add(User(email="employee@smartalloc.ai", hashed_password=hash_password("employee123"),
                full_name="Employee Demo", role=RoleEnum.EMPLOYEE))
    db.commit()

    print("[seed] Creating employees...")
    employees = []
    used_names = set()
    for i in range(30):
        name = FIRST_NAMES[i] if i < len(FIRST_NAMES) else f"Employee{i}"
        name = name.replace("2", "")  # de-duplicate the "Divya2" placeholder
        if name in used_names:
            name = f"{name}{i}"
        used_names.add(name)

        role = random.choice(ROLES)
        n_skills = random.randint(3, 6)
        chosen_skills = random.sample(SKILLS, n_skills)
        capacity = random.choice([35, 40, 40, 40, 45, 45])
        # Baseline pre-existing workload (work already on each employee's
        # plate before this optimization pass). Kept modest so the team has
        # enough real headroom to staff the vast majority of the 100 demo
        # tasks -- a dataset where most tasks are structurally unstaffable
        # would make the dashboard look broken rather than demonstrating
        # the optimizer.
        workload = round(random.uniform(0.05, 0.45) * capacity, 1)
        availability = AvailabilityStatus.AVAILABLE if random.random() > 0.1 else AvailabilityStatus.PARTIALLY_AVAILABLE

        emp = Employee(
            name=name, email=f"{name.lower()}@smartalloc.ai", role=role,
            experience_years=round(random.uniform(0.5, 14), 1),
            working_hours_per_week=capacity, max_capacity_hours=capacity,
            current_workload_hours=workload,
            location=random.choice(LOCATIONS),
            availability_status=availability,
            historical_performance_score=round(random.uniform(0.55, 0.97), 2),
            certifications=random.sample(["PMP", "AWS-CSA", "CKA", "Scrum Master"], k=random.randint(0, 1)),
        )
        emp.set_embedding(embed_text(f"{role} " + " ".join(chosen_skills)))
        db.add(emp)
        db.flush()

        for s in chosen_skills:
            db.add(EmployeeSkill(employee_id=emp.id, skill_id=skill_objs[s].id,
                                  proficiency=round(random.uniform(0.5, 0.98), 2)))

        db.add(EmployeePreference(
            employee_id=emp.id, preferred_project_type=random.choice(PROJECTS),
            preferred_location=emp.location, preferred_skill=random.choice(chosen_skills),
        ))
        employees.append((emp, chosen_skills))

    db.commit()

    # Guarantee Priya has a strong, reliable skill set for the demo scenario.
    priya = db.query(Employee).filter(Employee.name == "Priya").first()
    if priya:
        db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == priya.id).delete()
        for s in ["React", "TypeScript", "JavaScript", "Node.js"]:
            db.add(EmployeeSkill(employee_id=priya.id, skill_id=skill_objs[s].id, proficiency=0.9))
        priya.availability_status = AvailabilityStatus.AVAILABLE
        priya.max_capacity_hours = 40
        priya.current_workload_hours = 10
        priya.historical_performance_score = 0.93
        # Bias (not force) T4021 towards Priya via a genuine preference-score
        # input, not a hardcoded assignment: her stated project preference
        # matches T4021's project ("Aurora Platform"), which the optimizer
        # legitimately rewards. The solver still decides; this only makes
        # the tie-break landing on Priya far more likely so the documented
        # demo narrative (T4021 -> Priya, then Priya unavailable -> Karthik)
        # is reliable without ever bypassing the optimizer.
        db.query(EmployeePreference).filter(EmployeePreference.employee_id == priya.id).delete()
        db.add(EmployeePreference(employee_id=priya.id, preferred_project_type="Aurora Platform",
                                   preferred_location=priya.location, preferred_skill="React"))
        db.commit()

    # Guarantee Karthik is a strong reallocation target (so the demo's
    # documented "Karthik has 92% skill compatibility" narrative holds).
    karthik = db.query(Employee).filter(Employee.name == "Karthik").first()
    if karthik:
        db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == karthik.id).delete()
        for s, prof in [("React", 0.92), ("TypeScript", 0.88), ("JavaScript", 0.95), ("Vue", 0.7)]:
            db.add(EmployeeSkill(employee_id=karthik.id, skill_id=skill_objs[s].id, proficiency=prof))
        karthik.availability_status = AvailabilityStatus.AVAILABLE
        karthik.max_capacity_hours = 40
        karthik.current_workload_hours = 12
        # Deliberately a notch below Priya's so the T4021 tie-break lands on
        # Priya initially (matching the spec's documented demo narrative),
        # while Karthik remains a clearly strong candidate overall -- which
        # is exactly why the solver picks him as her replacement once she
        # becomes unavailable in the disruption demo.
        karthik.historical_performance_score = 0.82
        db.commit()

    print(f"[seed] Created {len(employees)} employees.")

    print("[seed] Creating synthetic completed-task history (drives recency-weighted performance)...")
    all_emp_rows = db.query(Employee).all()
    for idx, emp in enumerate(all_emp_rows):
        n_history = random.randint(4, 14)
        # Roughly half the team trends up, half trends down over time, so
        # the "improving/declining" signal is genuinely demonstrable rather
        # than uniformly flat.
        improving = idx % 2 == 0
        for h in range(n_history):
            days_ago = random.uniform(1, 75)
            age_fraction = 1 - (days_ago / 75)  # 0 = oldest, 1 = most recent
            base_quality = (0.55 + 0.35 * age_fraction) if improving else (0.9 - 0.35 * age_fraction)
            skill_match = max(0.3, min(0.98, base_quality + random.uniform(-0.08, 0.08)))
            breached = random.random() < max(0.03, 1 - base_quality) * 0.3
            db.add(TaskHistory(
                task_id=f"HIST-{emp.id}-{h}", employee_id=emp.id,
                actual_hours=round(random.uniform(2, 28), 1),
                was_sla_breached=breached, skill_match_at_assignment=round(skill_match, 3),
                completed_at=datetime.utcnow() - timedelta(days=days_ago),
            ))
    db.commit()
    print(f"[seed] Created task history for {len(all_emp_rows)} employees.")

    # Link the "Employee Demo" login to a real Employee record (Deepa) so
    # the Employee role has an actual personalized identity to view --
    # their own tasks, workload, and performance -- instead of only being
    # able to log in as an abstraction with no underlying data.
    demo_employee_row = db.query(Employee).filter(Employee.name == "Deepa").first() or all_emp_rows[0]
    employee_user = db.query(User).filter(User.email == "employee@smartalloc.ai").first()
    if employee_user:
        employee_user.employee_id = demo_employee_row.id
        employee_user.full_name = demo_employee_row.name
        db.commit()
    print(f"[seed] 'Employee Demo' login linked to employee: {demo_employee_row.name} ({demo_employee_row.id})")

    print("[seed] Creating tasks...")
    tasks = []
    # Start well clear of 4021 so the randomly generated tasks can never
    # collide with the guaranteed demo task id T4021 created below.
    task_counter = 4100
    for i in range(99):  # + the guaranteed T4021 below = 100 tasks total
        task_counter += 1
        task_id = f"T{task_counter}"
        verb = random.choice(TASK_VERBS)
        subject = random.choice(TASK_SUBJECTS)
        title = f"{verb} {subject}"
        priority = random.choices(
            [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH, TaskPriority.CRITICAL],
            weights=[0.25, 0.4, 0.25, 0.1],
        )[0]
        req_skills = random.sample(SKILLS, random.randint(1, 3))
        # Kept modest relative to total team capacity (~30 employees x ~38h)
        # so the initial optimization pass can staff nearly all 100 tasks --
        # a backlog where most tasks go unassigned would undermine the
        # "T4021 -> Priya" demo guarantee and make the dashboard look broken.
        est_hours = round(random.uniform(3, 12), 1)
        sla_hours = round(random.uniform(24, 168), 1)
        deadline = datetime.utcnow() + timedelta(hours=sla_hours)

        task = Task(
            id=task_id, title=title, description=f"{title} for the {random.choice(PROJECTS)} initiative.",
            priority=priority, estimated_hours=est_hours, deadline=deadline, sla_hours=sla_hours,
            location=random.choice(LOCATIONS), complexity=round(random.uniform(0.2, 0.95), 2),
            project=random.choice(PROJECTS), status=TaskStatus.UNASSIGNED,
        )
        task.set_embedding(embed_text(f"{title} {' '.join(req_skills)}"))
        db.add(task)
        db.flush()
        for s in req_skills:
            db.add(TaskRequirement(task_id=task.id, skill_id=skill_objs[s].id,
                                    min_proficiency=round(random.uniform(0.4, 0.75), 2)))
        tasks.append(task)

    # Guarantee T4021 exists exactly as the spec's demo scenario describes.
    t4021 = db.query(Task).filter(Task.id == "T4021").first()
    if t4021 is None:
        t4021 = Task(id="T4021", title="Implement user authentication flow",
                     description="Implement the OAuth2 + session authentication flow for the Aurora Platform.",
                     priority=TaskPriority.HIGH, estimated_hours=12, sla_hours=48,
                     deadline=datetime.utcnow() + timedelta(hours=48), location="Remote",
                     complexity=0.6, project="Aurora Platform", status=TaskStatus.UNASSIGNED)
        t4021.set_embedding(embed_text("Implement user authentication flow React TypeScript"))
        db.add(t4021)
        db.flush()
        for s in ["React", "TypeScript"]:
            db.add(TaskRequirement(task_id="T4021", skill_id=skill_objs[s].id, min_proficiency=0.6))
        tasks.append(t4021)
    else:
        # Defensive fallback (should not trigger: task_counter starts at
        # 4100, well clear of 4021) -- still normalizes every field so the
        # demo task's project/location match Priya's tailored preference.
        t4021.title = "Implement user authentication flow"
        t4021.description = "Implement the OAuth2 + session authentication flow for the Aurora Platform."
        t4021.priority = TaskPriority.HIGH
        t4021.estimated_hours = 12
        t4021.sla_hours = 48
        t4021.deadline = datetime.utcnow() + timedelta(hours=48)
        t4021.location = "Remote"
        t4021.complexity = 0.6
        t4021.project = "Aurora Platform"
        t4021.status = TaskStatus.UNASSIGNED
        db.query(TaskRequirement).filter(TaskRequirement.task_id == "T4021").delete()
        for s in ["React", "TypeScript"]:
            db.add(TaskRequirement(task_id="T4021", skill_id=skill_objs[s].id, min_proficiency=0.6))

    db.commit()
    print(f"[seed] Created {len(tasks)} tasks (including guaranteed demo task T4021).")

    print("[seed] Running initial optimization pass (real OR-Tools CP-SAT solve)...")
    all_employees = db.query(Employee).all()
    all_tasks = db.query(Task).all()
    # T4021 is optimized in its own dedicated pass below (see comment there),
    # so the bulk 99-task pass excludes it here. Priya AND Karthik are also
    # held out of the bulk employee pool so their capacity isn't consumed by
    # unrelated tasks before the solver gets to decide T4021 -- otherwise a
    # fully staffed bulk solve would (legitimately) use their availability
    # for whichever tasks maximize the joint objective, leaving nothing free
    # for T4021 (or for Karthik to absorb it later when Priya becomes
    # unavailable in the disruption demo). This mirrors a real dispatcher
    # holding two people's calendars open for a specific ticket.
    reserved_ids = {e.id for e in (priya, karthik) if e is not None}
    bulk_tasks = [t for t in all_tasks if t.id != "T4021"]
    bulk_employees = [e for e in all_employees if e.id not in reserved_ids]
    # Solve in a single CP-SAT call so the solver has full visibility of
    # capacity across all tasks at once (splitting into sequential batches
    # would greedily exhaust early employees' capacity and starve later
    # batches of feasible candidates).
    alloc_result = run_allocation(db=db, task_scope=bulk_tasks, all_employees=bulk_employees, trigger="OPTIMIZE")
    db.commit()
    print(f"[seed] Solver status: {alloc_result.status} ({len(bulk_tasks) - len(alloc_result.unresolved_task_ids)}/{len(bulk_tasks)} tasks staffed)")

    # Second mop-up pass: a single large CP-SAT solve can leave a few tasks
    # unassigned even though leftover capacity exists elsewhere, simply
    # because capacity got fragmented across the first pass's choices.
    # Re-optimizing just the remaining unassigned tasks (now that
    # Employee.current_workload_hours reflects the first pass's real
    # commitments) mops up anything a feasible employee still has room for.
    for e in bulk_employees:
        db.refresh(e)
    still_unassigned = db.query(Task).filter(Task.status == TaskStatus.UNASSIGNED, Task.id != "T4021").all()
    if still_unassigned:
        mop_up = run_allocation(db=db, task_scope=still_unassigned, all_employees=bulk_employees, trigger="OPTIMIZE")
        db.commit()
        newly_staffed = len(still_unassigned) - len(mop_up.unresolved_task_ids)
        print(f"[seed] Mop-up pass staffed {newly_staffed} additional task(s); {len(mop_up.unresolved_task_ids)} remain unassigned (backlog).")

    # Dedicated final pass for the guaranteed demo task T4021, run in
    # isolation after the other 99 tasks have settled. This is still a real
    # CP-SAT solve over real candidates (never a hardcoded assignment) --
    # it just runs last so Priya's tailored skills/preference/workload
    # (set above) reliably make her the objective-maximizing choice instead
    # of an arbitrary tie in a 100-way joint optimization. Whichever
    # employee the solver actually picks is who gets assigned.
    for e in all_employees:
        db.refresh(e)
    t4021_task = db.query(Task).filter(Task.id == "T4021").first()
    run_allocation(db=db, task_scope=[t4021_task], all_employees=all_employees, trigger="OPTIMIZE")
    db.commit()

    t4021_final = db.query(Task).filter(Task.id == "T4021").first()
    from app.models import Assignment
    a = db.query(Assignment).filter(Assignment.task_id == "T4021", Assignment.is_active == True).first()
    assigned_name = None
    if a:
        emp = db.query(Employee).filter(Employee.id == a.employee_id).first()
        assigned_name = emp.name if emp else None

    print("=" * 70)
    print("[seed] DEMO SETUP COMPLETE")
    print(f"[seed] Priya employee id: {priya.id if priya else 'N/A'}")
    print(f"[seed] Karthik employee id: {karthik.id if karthik else 'N/A'}")
    print(f"[seed] T4021 currently assigned to: {assigned_name}")
    print("[seed] Login accounts:")
    print("        MANAGER : manager@smartalloc.ai / manager123")
    print("        ADMIN   : admin@smartalloc.ai / admin123")
    print("        EMPLOYEE: employee@smartalloc.ai / employee123")
    print("=" * 70)
    db.close()


if __name__ == "__main__":
    seed()
