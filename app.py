"""Klear IQ — practice-to-game football grading."""
import csv
import io
import os
import secrets
from collections import defaultdict
from datetime import date, datetime
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'unsafe-local-development-key'),
    SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///klear_iq.db').replace('postgres://', 'postgresql://', 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
)
db = SQLAlchemy(app)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    jersey = db.Column(db.String(12), default='')
    position = db.Column(db.String(35), default='')
    active = db.Column(db.Boolean, default=True, nullable=False)

class GameWeek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.String(12), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    opponent = db.Column(db.String(120), nullable=False)
    game_date = db.Column(db.Date, nullable=True)
    location = db.Column(db.String(100), default='')
    sessions = db.relationship('GradingSession', backref='game_week', cascade='all,delete-orphan', order_by='GradingSession.session_date')
    __table_args__ = (UniqueConstraint('season','week', name='unique_season_week'),)

class GradingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('game_week.id'), nullable=False)
    kind = db.Column(db.String(12), nullable=False)  # practice or game
    session_date = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(90), default='')
    grades = db.relationship('Grade', backref='grading_session', cascade='all,delete-orphan')

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('grading_session.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    align = db.Column(db.Integer, nullable=False)
    assign = db.Column(db.Integer, nullable=False)
    tech = db.Column(db.Integer, nullable=False)
    effort = db.Column(db.Integer, nullable=False)
    overall = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    player = db.relationship('Player')
    __table_args__ = (UniqueConstraint('session_id','player_id', name='unique_session_player'),)
    @property
    def total(self):
        return sum((self.align,self.assign,self.tech,self.effort,self.overall))
    @property
    def tier(self):
        # These initial bands are defaults and must be confirmed against the team's BOSS/tier workbook.
        return ('Tier 4' if self.total >= 13 else 'Tier 3' if self.total >= 10 else
                'Tier 2' if self.total >= 7 else 'Tier 1')

def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def enforce_csrf():
    if request.method == 'POST' and not secrets.compare_digest(request.form.get('_csrf',''), session.get('_csrf','')):
        abort(400, description='Request expired or invalid. Refresh the page and try again.')

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped

@app.route('/health')
def health():
    return {'status':'ok', 'app':'Klear IQ'}

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        supplied = request.form.get('password','')
        hashed = os.environ.get('ADMIN_PASSWORD_HASH','')
        plain = os.environ.get('ADMIN_PASSWORD','')
        valid = (check_password_hash(hashed,supplied) if hashed else
                 (bool(plain) and secrets.compare_digest(plain,supplied)))
        if valid:
            session.clear()
            session['authenticated'] = True
            csrf_token()
            return redirect(url_for('home'))
        flash('Incorrect password or password not configured.', 'error')
    return render_template('login.html')

@app.route('/logout',methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/', methods=['GET','POST'])
@login_required
def home():
    if request.method == 'POST':
        opponent = request.form.get('opponent','').strip()[:120]
        season = request.form.get('season','').strip()[:12]
        week = request.form.get('week',type=int)
        raw_date = request.form.get('game_date','')
        if not opponent or not season or week is None or not (1 <= week <= 30):
            flash('Enter an opponent, season, and week (1–30).','error')
        else:
            try:
                game_date = date.fromisoformat(raw_date) if raw_date else None
                if GameWeek.query.filter_by(season=season,week=week).first():
                    flash('That season/week already exists.','error')
                else:
                    db.session.add(GameWeek(opponent=opponent,season=season,week=week,game_date=game_date,
                                            location=request.form.get('location','')[:100]))
                    db.session.commit()
                    flash('Game week created. Add your practice sessions and game session.','success')
            except ValueError:
                flash('Use a valid game date.','error')
        return redirect(url_for('home'))
    weeks = GameWeek.query.order_by(GameWeek.season.desc(), GameWeek.week.desc()).all()
    return render_template('home.html',weeks=weeks, today=date.today())

@app.route('/roster', methods=['GET','POST'])
@login_required
def roster():
    if request.method == 'POST':
        name = request.form.get('name','').strip()[:120]
        if name:
            db.session.add(Player(name=name,jersey=request.form.get('jersey','').strip()[:12],
                                  position=request.form.get('position','').strip()[:35]))
            db.session.commit()
            flash('Player added.','success')
        return redirect(url_for('roster'))
    return render_template('roster.html',players=Player.query.order_by(Player.name).all())

@app.route('/week/<int:week_id>', methods=['GET','POST'])
@login_required
def week(week_id):
    item = db.get_or_404(GameWeek,week_id)
    if request.method == 'POST':
        kind = request.form.get('kind','')
        try: session_date = date.fromisoformat(request.form.get('session_date',''))
        except ValueError: session_date = None
        if kind not in ('practice','game') or not session_date:
            flash('Choose Practice or Game and a valid date.','error')
        elif kind == 'game' and any(s.kind == 'game' for s in item.sessions):
            flash('One game session is allowed per week. Edit grades in the existing game session.','error')
        else:
            db.session.add(GradingSession(week_id=item.id,kind=kind,session_date=session_date,
                                          label=request.form.get('label','').strip()[:90]))
            db.session.commit()
            flash('Grading session created.','success')
        return redirect(url_for('week',week_id=week_id))
    return render_template('week.html',week=item,summary=week_summary(item),today=date.today())

@app.route('/session/<int:session_id>',methods=['GET','POST'])
@login_required
def grade_session(session_id):
    s = db.get_or_404(GradingSession,session_id)
    players = Player.query.filter_by(active=True).order_by(Player.name).all()
    if request.method == 'POST':
        p = db.session.get(Player,request.form.get('player_id',type=int))
        if not p or not p.active: abort(400)
        values={}
        for field in ('align','assign','tech','effort','overall'):
            number = request.form.get(field,type=int)
            if number is None or not 0 <= number <= 3: abort(400)
            values[field] = number
        grade = Grade.query.filter_by(session_id=s.id,player_id=p.id).first()
        if grade is None:
            grade=Grade(session_id=s.id,player_id=p.id,**values)
            db.session.add(grade)
        else:
            for field,value in values.items(): setattr(grade,field,value)
        grade.notes=request.form.get('notes','').strip()[:2000]
        db.session.commit()
        flash(f'Grade saved for {p.name}.','success')
        return redirect(url_for('grade_session',session_id=s.id))
    grades=Grade.query.filter_by(session_id=s.id).all()
    return render_template('session.html',session=s,players=players,grades=sorted(grades,key=lambda g:g.player.name.lower()))

def week_summary(week):
    by_player=defaultdict(lambda:{'practice':[],'game':[]})
    for s in week.sessions:
        for g in s.grades:
            by_player[g.player_id][s.kind].append(g.total)
    out=[]
    for pid,group in by_player.items():
        player=db.session.get(Player,pid)
        if not player: continue
        practice = round(sum(group['practice'])/len(group['practice']),2) if group['practice'] else None
        game = round(sum(group['game'])/len(group['game']),2) if group['game'] else None
        out.append({'player':player,'practice':practice,'game':game,'delta':round(game-practice,2) if practice is not None and game is not None else None,
                    'sessions':len(group['practice'])+len(group['game'])})
    return sorted(out,key=lambda x:x['player'].name.lower())

@app.route('/week/<int:week_id>/csv')
@login_required
def weekly_csv(week_id):
    w=db.get_or_404(GameWeek,week_id)
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['Season','Week','Opponent','Session type','Session date','Session label','Player','Jersey','Position','Align','Assign','Tech','Effort','Overall','Total / 15','Tier','Notes'])
    for s in w.sessions:
        for g in sorted(s.grades,key=lambda x:x.player.name.lower()):
            p=g.player
            writer.writerow([w.season,w.week,w.opponent,s.kind,s.session_date.isoformat(),s.label,p.name,p.jersey,p.position,
                             g.align,g.assign,g.tech,g.effort,g.overall,g.total,g.tier,g.notes])
    return send_file(io.BytesIO(stream.getvalue().encode('utf-8-sig')),as_attachment=True,mimetype='text/csv',
                     download_name=f'klear-iq-{w.season}-week-{w.week}-grades.csv')

@app.route('/week/<int:week_id>/summary.csv')
@login_required
def summary_csv(week_id):
    w=db.get_or_404(GameWeek,week_id)
    stream=io.StringIO(); writer=csv.writer(stream)
    writer.writerow(['Season','Week','Opponent','Player','Jersey','Position','Practice avg / 15','Game avg / 15','Game minus practice','Graded sessions'])
    for r in week_summary(w):
        p=r['player'];writer.writerow([w.season,w.week,w.opponent,p.name,p.jersey,p.position,r['practice'],r['game'],r['delta'],r['sessions']])
    return send_file(io.BytesIO(stream.getvalue().encode('utf-8-sig')),as_attachment=True,mimetype='text/csv',
                     download_name=f'klear-iq-{w.season}-week-{w.week}-summary.csv')

@app.route('/season')
@login_required
def season():
    weeks = GameWeek.query.order_by(GameWeek.season.desc(),GameWeek.week).all()
    by_season=defaultdict(lambda:defaultdict(lambda:{'practice':[],'game':[]}))
    for w in weeks:
        for s in w.sessions:
            for g in s.grades:
                by_season[w.season][g.player_id][s.kind].append(g.total)
    data=[]
    for year,players in sorted(by_season.items(), reverse=True):
        for pid,values in players.items():
            p=db.session.get(Player,pid)
            if not p:continue
            data.append({'year':year,'player':p,'practice':round(sum(values['practice'])/len(values['practice']),2) if values['practice'] else None,
                         'game':round(sum(values['game'])/len(values['game']),2) if values['game'] else None,
                         'count':len(values['practice'])+len(values['game'])})
    return render_template('season.html',rows=sorted(data,key=lambda r:(r['year'],r['player'].name),reverse=True))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG')=='1')
