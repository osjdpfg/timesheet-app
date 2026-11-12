from sqlalchemy import func
from ..database.db import get_session
from ..database.models import Document, DocumentRow, DocumentCell, ManualOverride


def create_document(doc_type, group, year, month, employees, source_document_id=None):
    s = get_session()
    try:
        max_inst = s.query(func.max(Document.instance_number)).filter_by(
            doc_type=doc_type, group=group, year=year, month=month
        ).scalar()
        new_inst = 0 if max_inst is None else max_inst + 1

        doc = Document(doc_type=doc_type, group=group, year=year, month=month, 
                       instance_number=new_inst, linked_schedule_id=source_document_id)
        s.add(doc)
        s.flush()

        source_cells = {}
        if source_document_id:
            src = s.get(Document, source_document_id)
            if src:
                for r in src.rows:
                    source_cells[(r.employee_name, r.employee_position)] = \
                        {c.day: c.code for c in r.cells}

        for name, pos, auto_7h in employees:
            row = DocumentRow(document_id=doc.id, employee_name=name,
                              employee_position=pos, auto_7h=auto_7h)
            s.add(row)
            s.flush()
            src = source_cells.get((name, pos), {})
            for day in range(1, 32):
                s.add(DocumentCell(row_id=row.id, day=day,
                                   code=src.get(day, "")))
        s.commit()
        return doc.id
    finally:
        s.close()


def get_linked_timesheets(doc_id):
    s = get_session()
    try:
        return s.query(Document).filter_by(linked_schedule_id=doc_id).all()
    finally:
        s.close()


def update_document_structure(doc_id, new_year, new_month, employees):
    s = get_session()
    try:
        doc = s.get(Document, doc_id)
        if not doc: return False
        
        doc.year = new_year
        doc.month = new_month
        
        existing_rows = { (r.employee_name, r.employee_position): r for r in doc.rows }
        new_rows = []
        
        for name, pos, auto_7h in employees:
            if (name, pos) in existing_rows:
                row = existing_rows.pop((name, pos))
                row.auto_7h = auto_7h
                new_rows.append(row)
            else:
                row = DocumentRow(document_id=doc.id, employee_name=name, employee_position=pos, auto_7h=auto_7h)
                s.add(row)
                s.flush()
                for day in range(1, 32):
                    s.add(DocumentCell(row_id=row.id, day=day, code=""))
                new_rows.append(row)
        
        for row in existing_rows.values():
            s.delete(row)
            
        if doc.doc_type == "schedule":
            timesheets = s.query(Document).filter_by(linked_schedule_id=doc.id).all()
            for ts in timesheets:
                ts.year = new_year
                ts.month = new_month
                
                ts_existing = { (r.employee_name, r.employee_position): r for r in ts.rows }
                ts_new_rows = []
                
                for row in new_rows:
                    if (row.employee_name, row.employee_position) in ts_existing:
                        ts_row = ts_existing.pop((row.employee_name, row.employee_position))
                        ts_row.auto_7h = row.auto_7h
                        ts_new_rows.append(ts_row)
                    else:
                        ts_row = DocumentRow(document_id=ts.id, employee_name=row.employee_name, employee_position=row.employee_position, auto_7h=row.auto_7h)
                        s.add(ts_row)
                        s.flush()
                        # КОПИРУЕМ ЯЧЕЙКИ из графика для нового сотрудника
                        src_cells = {c.day: c.code for c in row.cells}
                        for day in range(1, 32):
                            s.add(DocumentCell(row_id=ts_row.id, day=day, code=src_cells.get(day, "")))
                        ts_new_rows.append(ts_row)
                
                for ts_row in ts_existing.values():
                    s.delete(ts_row)
        
        s.commit()
        return True
    finally:
        s.close()


def list_documents(doc_type=None, group=None):
    s = get_session()
    try:
        q = s.query(Document)
        if doc_type:
            q = q.filter_by(doc_type=doc_type)
        if group:
            q = q.filter_by(group=group)
        return [(d.id, d.doc_type, d.group, d.year, d.month, d.instance_number)
                for d in q.order_by(Document.year.desc(),
                                    Document.month.desc()).all()]
    finally:
        s.close()


def delete_document(doc_id):
    s = get_session()
    try:
        d = s.get(Document, doc_id)
        if d:
            s.delete(d)
            s.commit()
    finally:
        s.close()


def load_document(doc_id):
    s = get_session()
    try:
        d = s.get(Document, doc_id)
        if not d:
            return None
        return {
            "id": d.id,
            "doc_type": d.doc_type,
            "group": d.group,
            "year": d.year,
            "month": d.month,
            "instance_number": d.instance_number,
            "manual_mode": d.manual_mode,
            "rows": [{
                "id": r.id,
                "employee_name": r.employee_name,
                "employee_position": r.employee_position,
                "auto_7h": r.auto_7h,
                "cells": {c.day: c.code for c in r.cells},
                "overrides": {o.column_key: o.value for o in r.overrides},
            } for r in d.rows],
        }
    finally:
        s.close()


def save_document(doc_id, rows_data, manual_mode):
    s = get_session()
    try:
        d = s.get(Document, doc_id)
        if not d:
            return
        d.manual_mode = manual_mode
        
        # 1. Сохраняем сам документ
        for rd in rows_data:
            row = s.get(DocumentRow, rd["id"])
            if not row:
                continue
            cmap = {c.day: c for c in row.cells}
            for day, code in rd["cells"].items():
                if day in cmap:
                    cmap[day].code = code
                else:
                    s.add(DocumentCell(row_id=row.id, day=day, code=code))
            omap = {o.column_key: o for o in row.overrides}
            for key in list(omap.keys()):
                if key not in rd["overrides"]:
                    s.delete(omap[key])
            for key, val in rd["overrides"].items():
                if key in omap:
                    omap[key].value = val
                else:
                    s.add(ManualOverride(row_id=row.id, column_key=key, value=val))
                    
        s.flush()
        
        # 2. Если это график, синхронизируем данные с привязанными табелями
        if d.doc_type == "schedule":
            timesheets = s.query(Document).filter_by(linked_schedule_id=doc_id).all()
            for ts in timesheets:
                if ts.manual_mode:
                    continue # Не трогаем табель, если он в ручном режиме
                    
                ts_rows = { (r.employee_name, r.employee_position): r for r in ts.rows }
                
                for rd in rows_data:
                    sched_row = s.get(DocumentRow, rd["id"])
                    if not sched_row: continue
                    
                    key = (sched_row.employee_name, sched_row.employee_position)
                    if key in ts_rows:
                        ts_row = ts_rows[key]
                        ts_cmap = {c.day: c for c in ts_row.cells}
                        for day, code in rd["cells"].items():
                            if day in ts_cmap:
                                ts_cmap[day].code = code
                            else:
                                s.add(DocumentCell(row_id=ts_row.id, day=day, code=code))
                                
        s.commit()
    finally:
        s.close()
