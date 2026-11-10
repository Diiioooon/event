import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect

app = Flask(__name__)
DB = "Registration.db"


# ---------- database ----------
def run(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(sql, params)
        con.commit()
        rows = cur.fetchall()
    finally:
        con.close()
    return rows


def create_tables():
    run("""CREATE TABLE IF NOT EXISTS Events (
            evCode INTEGER PRIMARY KEY,
            evName TEXT,
            evDate TEXT,
            evVenue TEXT,
            evRFee REAL)""")
    run("""CREATE TABLE IF NOT EXISTS Participants (
            partID INTEGER PRIMARY KEY,
            evCode INTEGER,
            partFName TEXT,
            partLName TEXT,
            partDRate REAL,
            FOREIGN KEY (evCode) REFERENCES Events(evCode))""")
    run("""CREATE TABLE IF NOT EXISTS Registration (
            regCode INTEGER PRIMARY KEY AUTOINCREMENT,
            partID INTEGER,
            regDate TEXT,
            regFPaid REAL,
            regPMode TEXT,
            FOREIGN KEY (partID) REFERENCES Participants(partID))""")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def search_events(q):
    like = "%" + q + "%"
    return run("""SELECT * FROM Events
                  WHERE evName LIKE ? OR CAST(evCode AS TEXT) LIKE ?
                  ORDER BY evCode""", (like, like))


def search_participants(q):
    like = "%" + q + "%"
    return run("""SELECT * FROM Participants
                  WHERE partFName LIKE ? OR partLName LIKE ?
                  OR CAST(partID AS TEXT) LIKE ?
                  ORDER BY partID""", (like, like, like))


# ---------- menu ----------
@app.route("/")
def index():
    return render_template("index.html")


# ======================= EVENTS =======================
@app.route("/events")
def events():
    rows = run("SELECT * FROM Events ORDER BY evCode")
    return render_template("events.html", rows=rows)


@app.route("/events/add", methods=["GET", "POST"])
def event_add():
    if request.method == "POST":
        try:
            run("INSERT INTO Events VALUES (?, ?, ?, ?, ?)",
                (request.form["evCode"], request.form["evName"],
                 request.form["evDate"], request.form["evVenue"],
                 request.form["evRFee"]))
        except sqlite3.IntegrityError:
            return render_template("event_add.html", error="Event code already exists.")
        return redirect("/events")
    return render_template("event_add.html", error="")


@app.route("/events/update")
def event_update():
    q = request.args.get("q", "")
    rows = search_events(q)
    return render_template("event_update.html", rows=rows, q=q)


@app.route("/events/edit/<code>", methods=["GET", "POST"])
def event_edit(code):
    if request.method == "POST":
        run("UPDATE Events SET evName=?, evDate=?, evVenue=?, evRFee=? WHERE evCode=?",
            (request.form["evName"], request.form["evDate"],
             request.form["evVenue"], request.form["evRFee"], code))
        return redirect("/events/update")
    e = run("SELECT * FROM Events WHERE evCode=?", (code,))[0]
    return render_template("event_edit.html", e=e)


@app.route("/events/delete")
def event_delete():
    q = request.args.get("q", "")
    error = request.args.get("error", "")
    rows = search_events(q)
    return render_template("event_delete.html", rows=rows, q=q, error=error)


@app.route("/events/remove/<code>")
def event_remove(code):
    try:
        run("DELETE FROM Events WHERE evCode=?", (code,))
    except sqlite3.IntegrityError:
        return redirect("/events/delete?error=Event still has participants.")
    return redirect("/events/delete")


# ===================== PARTICIPANTS =====================
@app.route("/participants")
def participants():
    rows = run("SELECT * FROM Participants ORDER BY partID")
    return render_template("participants.html", rows=rows)


@app.route("/participants/add", methods=["GET", "POST"])
def participant_add():
    evs = run("SELECT evCode, evName FROM Events")
    if request.method == "POST":
        try:
            run("INSERT INTO Participants VALUES (?, ?, ?, ?, ?)",
                (request.form["partID"], request.form["evCode"],
                 request.form["partFName"], request.form["partLName"],
                 request.form["partDRate"]))
        except sqlite3.IntegrityError:
            return render_template("participant_add.html", evs=evs,
                                   error="Participant ID already exists.")
        return redirect("/participants")
    return render_template("participant_add.html", evs=evs, error="")


@app.route("/participants/update")
def participant_update():
    q = request.args.get("q", "")
    rows = search_participants(q)
    return render_template("participant_update.html", rows=rows, q=q)


@app.route("/participants/edit/<pid>", methods=["GET", "POST"])
def participant_edit(pid):
    evs = run("SELECT evCode, evName FROM Events")
    if request.method == "POST":
        run("""UPDATE Participants SET evCode=?, partFName=?, partLName=?, partDRate=?
               WHERE partID=?""",
            (request.form["evCode"], request.form["partFName"],
             request.form["partLName"], request.form["partDRate"], pid))
        return redirect("/participants/update")
    p = run("SELECT * FROM Participants WHERE partID=?", (pid,))[0]
    return render_template("participant_edit.html", p=p, evs=evs)


@app.route("/participants/delete")
def participant_delete():
    q = request.args.get("q", "")
    error = request.args.get("error", "")
    rows = search_participants(q)
    return render_template("participant_delete.html", rows=rows, q=q, error=error)


@app.route("/participants/remove/<pid>")
def participant_remove(pid):
    try:
        run("DELETE FROM Participants WHERE partID=?", (pid,))
    except sqlite3.IntegrityError:
        return redirect("/participants/delete?error=Participant has registration records.")
    return redirect("/participants/delete")


# ===================== REGISTRATION =====================
@app.route("/registration")
def registration():
    # latest to oldest
    rows = run("""SELECT Registration.regCode, Registration.partID,
                         Participants.partFName, Participants.partLName,
                         Events.evName, Registration.regDate,
                         Registration.regFPaid, Registration.regPMode
                  FROM Registration, Participants, Events
                  WHERE Registration.partID = Participants.partID
                  AND Participants.evCode = Events.evCode
                  ORDER BY Registration.regDate DESC, Registration.regCode DESC""")
    return render_template("registration.html", rows=rows)


@app.route("/registration/add", methods=["GET", "POST"])
def registration_add():
    parts = run("""SELECT Participants.partID, Participants.partLName,
                          Participants.partFName, Events.evName,
                          Events.evRFee, Participants.partDRate
                   FROM Participants, Events
                   WHERE Participants.evCode = Events.evCode
                   ORDER BY Participants.partID""")
    if request.method == "POST":
        pid = request.form["partID"]
        already = run("SELECT regCode FROM Registration WHERE partID=?", (pid,))
        if len(already) > 0:
            return render_template("registration_add.html", parts=parts,
                                   today=today(), error="Participant is already registered.")
        found = run("""SELECT Events.evRFee, Participants.partDRate
                       FROM Participants, Events
                       WHERE Participants.evCode = Events.evCode
                       AND Participants.partID = ?""", (pid,))
        # fee paid = event fee - participant discount
        fee = found[0][0] - found[0][1]
        if fee < 0:
            fee = 0
        run("INSERT INTO Registration (partID, regDate, regFPaid, regPMode) VALUES (?, ?, ?, ?)",
            (pid, request.form["regDate"], fee, request.form["regPMode"]))
        return redirect("/registration")
    return render_template("registration_add.html", parts=parts, today=today(), error="")


# ===================== MONITORING =====================
@app.route("/monitor")
def monitor():
    evs = run("SELECT evCode, evName FROM Events ORDER BY evName")
    ev_code = request.args.get("ev_code", "")
    event = None
    records = []
    count = 0
    total_paid = 0
    discounts = 0
    if ev_code != "":
        event = run("SELECT * FROM Events WHERE evCode=?", (ev_code,))[0]
        rows = run("""SELECT Participants.partFName, Participants.partLName,
                             Registration.regDate, Registration.regFPaid
                      FROM Registration, Participants
                      WHERE Registration.partID = Participants.partID
                      AND Participants.evCode = ?
                      ORDER BY Registration.regDate DESC, Registration.regCode DESC""",
                   (ev_code,))
        for r in rows:
            full_name = r[0] + " " + r[1]
            records.append([full_name, r[2], r[3]])
        # aggregate functions
        agg = run("""SELECT COUNT(*), SUM(Registration.regFPaid)
                     FROM Registration, Participants
                     WHERE Registration.partID = Participants.partID
                     AND Participants.evCode = ?""", (ev_code,))
        count = agg[0][0]
        total_paid = agg[0][1]
        if total_paid is None:
            total_paid = 0
        # (a * evRFee) - b
        discounts = (count * event[4]) - total_paid
    return render_template("monitor.html", evs=evs, ev_code=ev_code, event=event,
                           records=records, count=count,
                           total_paid=round(total_paid, 2),
                           discounts=round(discounts, 2))


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
