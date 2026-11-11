from ..database.db import get_session
from ..database.models import Employee


def list_employees(group=None):
    s = get_session()
    try:
        q = s.query(Employee)
        if group:
            q = q.filter_by(group=group)
        return [(e.id, e.full_name, e.position, e.group, e.is_signatory, e.auto_7h)
                for e in q.order_by(Employee.full_name).all()]
    finally:
        s.close()


def add_employee(name, position, group, is_signatory=False, auto_7h=False):
    s = get_session()
    try:
        e = Employee(full_name=name, position=position, group=group,
                     is_signatory=is_signatory, auto_7h=auto_7h)
        s.add(e)
        s.commit()
        return e.id
    finally:
        s.close()


def update_employee(eid, name, position, group, is_signatory, auto_7h):
    s = get_session()
    try:
        e = s.get(Employee, eid)
        if e:
            e.full_name = name
            e.position = position
            e.group = group
            e.is_signatory = is_signatory
            e.auto_7h = auto_7h
            s.commit()
    finally:
        s.close()


def delete_employee(eid):
    s = get_session()
    try:
        e = s.get(Employee, eid)
        if e:
            s.delete(e)
            s.commit()
    finally:
        s.close()


def get_signatory(group):
    s = get_session()
    try:
        e = s.query(Employee).filter_by(group=group, is_signatory=True).first()
        return (e.full_name, e.position) if e else ("", "")
    finally:
        s.close()
