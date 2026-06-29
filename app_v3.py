from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, g
from datetime import datetime, date, timedelta
import sqlite3, os, hashlib, json

app = Flask(__name__)
app.secret_key = 'portalgate_toiti_v2_2024'
DB = 'portalgate.db'

# ─── DB ──────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        -- Empresas (tenants)
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT,
            logo_url TEXT,
            tema TEXT DEFAULT 'dark',
            cor_primaria TEXT DEFAULT '#3b82f6',
            plano TEXT DEFAULT 'basic',
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Postos (sub-tenants de uma empresa)
        CREATE TABLE IF NOT EXISTS postos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            endereco TEXT,
            cliente_nome TEXT,
            ativo INTEGER DEFAULT 1,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        );

        -- Usuários
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            posto_id INTEGER,
            nome TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'portaria',
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Visitantes
        CREATE TABLE IF NOT EXISTS visitantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            posto_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            documento TEXT,
            empresa_origem TEXT,
            destino TEXT,
            placa_veiculo TEXT,
            motivo TEXT,
            entrada TIMESTAMP,
            saida TIMESTAMP,
            operador_id INTEGER
        );

        -- Veículos da frota
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            posto_id INTEGER,
            placa TEXT NOT NULL,
            modelo TEXT NOT NULL,
            marca TEXT,
            ano INTEGER,
            cor TEXT,
            tipo TEXT,
            km_atual REAL DEFAULT 0,
            ativo INTEGER DEFAULT 1
        );

        -- Registros de uso de frota
        CREATE TABLE IF NOT EXISTS registros_frota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            veiculo_id INTEGER NOT NULL,
            motorista_id INTEGER NOT NULL,
            destino TEXT NOT NULL,
            motivo TEXT,
            km_saida REAL,
            km_chegada REAL,
            saida TIMESTAMP,
            chegada TIMESTAMP,
            checklist_saida TEXT,
            checklist_chegada TEXT,
            obs TEXT,
            operador_id INTEGER
        );

        -- Vigilantes / funcionários (por empresa de segurança)
        CREATE TABLE IF NOT EXISTS vigilantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            posto_id INTEGER,
            nome TEXT NOT NULL,
            matricula TEXT,
            cpf TEXT,
            cargo TEXT DEFAULT 'Vigilante',
            cnh TEXT,
            cnh_validade DATE,
            habilitado_frota INTEGER DEFAULT 0,
            curso_defensiva INTEGER DEFAULT 0,
            data_curso_defensiva DATE,
            aso_validade DATE,
            curso_vigilante DATE,
            porte_arma INTEGER DEFAULT 0,
            porte_validade DATE,
            nrs TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Master admin (você - Toiti)
    senha = hashlib.sha256('toiti@master'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO usuarios (nome,login,senha,perfil) VALUES (?,?,?,?)",
              ('Toiti Master','toiti', senha,'master'))

    # Empresa demo
    c.execute("INSERT OR IGNORE INTO empresas (id,nome,cnpj,tema,cor_primaria,plano) VALUES (?,?,?,?,?,?)",
              (1,'Segurança Alpha Ltda','12.345.678/0001-90','dark','#3b82f6','pro'))
    c.execute("INSERT OR IGNORE INTO empresas (id,nome,cnpj,tema,cor_primaria,plano) VALUES (?,?,?,?,?,?)",
              (2,'Vigilância Beta S/A','98.765.432/0001-10','light','#6366f1','basic'))

    # Postos
    c.execute("INSERT OR IGNORE INTO postos (id,empresa_id,nome,cliente_nome) VALUES (?,?,?,?)",
              (1,1,'Posto Central','Fábrica Exemplo Ltda'))
    c.execute("INSERT OR IGNORE INTO postos (id,empresa_id,nome,cliente_nome) VALUES (?,?,?,?)",
              (2,1,'Posto Portão Norte','Tuberfil Ind.'))
    c.execute("INSERT OR IGNORE INTO postos (id,empresa_id,nome,cliente_nome) VALUES (?,?,?,?)",
              (3,2,'Posto Único','Galpão Logística'))

    # Usuários demo
    def pw(p): return hashlib.sha256(p.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO usuarios (empresa_id,posto_id,nome,login,senha,perfil) VALUES (?,?,?,?,?,?)",
              (1,None,'Supervisor Alpha','supervisor1',pw('alpha123'),'supervisor'))
    c.execute("INSERT OR IGNORE INTO usuarios (empresa_id,posto_id,nome,login,senha,perfil) VALUES (?,?,?,?,?,?)",
              (1,1,'Porteiro João','porteiro1',pw('port123'),'portaria'))
    c.execute("INSERT OR IGNORE INTO usuarios (empresa_id,posto_id,nome,login,senha,perfil) VALUES (?,?,?,?,?,?)",
              (1,1,'Seg Trabalho Alpha','seg1',pw('seg123'),'seguranca'))
    c.execute("INSERT OR IGNORE INTO usuarios (empresa_id,posto_id,nome,login,senha,perfil) VALUES (?,?,?,?,?,?)",
              (2,3,'Supervisor Beta','supervisor2',pw('beta123'),'supervisor'))

    # Veículos demo
    c.execute("INSERT OR IGNORE INTO veiculos (id,empresa_id,posto_id,placa,modelo,marca,ano,cor,tipo,km_atual) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (1,1,1,'ABC-1234','Strada','Fiat',2022,'Branca','Pickup',45230))
    c.execute("INSERT OR IGNORE INTO veiculos (id,empresa_id,posto_id,placa,modelo,marca,ano,cor,tipo,km_atual) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (2,1,2,'DEF-5678','S10','Chevrolet',2021,'Prata','Pickup',82100))

    # Vigilantes demo
    c.execute("INSERT OR IGNORE INTO vigilantes (empresa_id,posto_id,nome,matricula,cargo,aso_validade,curso_vigilante,porte_arma,porte_validade,nrs) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (1,1,'Carlos Mendes','VIG001','Vigilante Líder','2025-08-15','2024-01-10',1,'2025-12-31','NR-1,NR-6'))
    c.execute("INSERT OR IGNORE INTO vigilantes (empresa_id,posto_id,nome,matricula,cargo,aso_validade,curso_vigilante,porte_arma,nrs) VALUES (?,?,?,?,?,?,?,?,?)",
              (1,1,'Ana Paula','VIG002','Vigilante','2024-11-01','2023-06-20',0,'NR-1'))
    c.execute("INSERT OR IGNORE INTO vigilantes (empresa_id,posto_id,nome,matricula,cargo,aso_validade,curso_vigilante,porte_arma,porte_validade,cnh,cnh_validade,habilitado_frota,curso_defensiva) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (1,2,'Roberto Lima','VIG003','Motorista Vigilante','2025-03-20','2023-09-15',0,None,'B','2026-04-10',1,1))

    conn.commit()
    conn.close()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def current_empresa():
    if session.get('perfil') == 'master':
        eid = request.args.get('eid') or session.get('eid_view')
        return int(eid) if eid else None
    return session.get('empresa_id')

def current_posto():
    if session.get('perfil') in ['master','supervisor']:
        pid = request.args.get('pid') or session.get('pid_view')
        return int(pid) if pid else None
    return session.get('posto_id')

def get_empresa_config(empresa_id):
    if not empresa_id:
        return {'tema':'dark','cor_primaria':'#3b82f6','nome':'PortalGate'}
    conn = get_db()
    e = conn.execute("SELECT * FROM empresas WHERE id=?", (empresa_id,)).fetchone()
    conn.close()
    return dict(e) if e else {'tema':'dark','cor_primaria':'#3b82f6','nome':'PortalGate'}

def login_required(perfis=None):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if perfis and session.get('perfil') not in perfis and session.get('perfil') not in ['master']:
                flash('Acesso não autorizado para seu perfil.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        login_val = request.form['login']
        senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
        conn = get_db()
        u = conn.execute("SELECT * FROM usuarios WHERE login=? AND senha=? AND ativo=1", (login_val,senha)).fetchone()
        conn.close()
        if u:
            session['user_id'] = u['id']
            session['nome'] = u['nome']
            session['perfil'] = u['perfil']
            session['empresa_id'] = u['empresa_id']
            session['posto_id'] = u['posto_id']
            return redirect(url_for('dashboard'))
        flash('Login ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required()
def dashboard():
    conn = get_db()
    hoje = date.today().isoformat()
    eid = current_empresa()
    pid = current_posto()
    cfg = get_empresa_config(eid)

    def q(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    # Queries simples sem filtro dinâmico - filtra em Python depois se necessário
    # Usa parâmetro OR para ignorar filtro quando eid/pid é None
    eid_p = eid or 0
    pid_p = pid or 0

    stats = {
        'visitantes_hoje':   q("SELECT COUNT(*) FROM visitantes WHERE DATE(entrada)=? AND (empresa_id=? OR ?=0) AND (posto_id=? OR ?=0)", (hoje, eid_p, eid_p, pid_p, pid_p)),
        'dentro_agora':      q("SELECT COUNT(*) FROM visitantes WHERE saida IS NULL AND entrada IS NOT NULL AND (empresa_id=? OR ?=0) AND (posto_id=? OR ?=0)", (eid_p, eid_p, pid_p, pid_p)),
        'veiculos_fora':     q("SELECT COUNT(*) FROM registros_frota WHERE chegada IS NULL AND saida IS NOT NULL AND (empresa_id=? OR ?=0)", (eid_p, eid_p)),
        'vigilantes_ativos': q("SELECT COUNT(*) FROM vigilantes WHERE ativo=1 AND (empresa_id=? OR ?=0) AND (posto_id=? OR ?=0)", (eid_p, eid_p, pid_p, pid_p)),
        'aso_vencendo':      q("SELECT COUNT(*) FROM vigilantes WHERE aso_validade <= date('now','+30 days') AND ativo=1 AND (empresa_id=? OR ?=0)", (eid_p, eid_p)),
        'porte_vencendo':    q("SELECT COUNT(*) FROM vigilantes WHERE porte_arma=1 AND porte_validade <= date('now','+60 days') AND ativo=1 AND (empresa_id=? OR ?=0)", (eid_p, eid_p)),
    }

    visitantes_ativos = conn.execute(
        "SELECT * FROM visitantes WHERE saida IS NULL AND entrada IS NOT NULL AND (empresa_id=? OR ?=0) AND (posto_id=? OR ?=0) ORDER BY entrada DESC LIMIT 10",
        (eid_p, eid_p, pid_p, pid_p)
    ).fetchall()

    frota_ativa = conn.execute("""
        SELECT rf.*, v.placa, v.modelo, vig.nome as motorista
        FROM registros_frota rf
        JOIN veiculos v ON v.id=rf.veiculo_id
        JOIN vigilantes vig ON vig.id=rf.motorista_id
        WHERE rf.chegada IS NULL AND rf.saida IS NOT NULL
        AND (rf.empresa_id=? OR ?=0)
        ORDER BY rf.saida DESC
    """, (eid_p, eid_p)).fetchall()

    # Para master: lista de empresas e postos
    empresas = conn.execute("SELECT * FROM empresas WHERE ativo=1").fetchall() if session['perfil']=='master' else []
    postos = []
    if eid:
        postos = conn.execute("SELECT * FROM postos WHERE empresa_id=? AND ativo=1", (eid,)).fetchall()

    conn.close()
    return render_template('dashboard.html', stats=stats, visitantes_ativos=visitantes_ativos,
                           frota_ativa=frota_ativa, cfg=cfg, empresas=empresas, postos=postos,
                           eid=eid, pid=pid)

# ─── PORTARIA ─────────────────────────────────────────────────────────────────

@app.route('/portaria')
@login_required(['portaria','supervisor','master'])
def portaria():
    conn = get_db()
    eid = current_empresa()
    pid = current_posto()
    cfg = get_empresa_config(eid)
    postos = conn.execute("SELECT * FROM postos WHERE empresa_id=? AND ativo=1",(eid,)).fetchall() if eid else []

    eid_p = eid or 0
    pid_p = pid or 0
    registros = conn.execute(
        "SELECT v.*, p.nome as posto_nome FROM visitantes v LEFT JOIN postos p ON p.id=v.posto_id WHERE (v.empresa_id=? OR ?=0) AND (v.posto_id=? OR ?=0) ORDER BY v.entrada DESC LIMIT 100",
        (eid_p, eid_p, pid_p, pid_p)
    ).fetchall()
    conn.close()
    return render_template('portaria.html', registros=registros, cfg=cfg, postos=postos, pid=pid)

@app.route('/portaria/entrada', methods=['POST'])
@login_required(['portaria','supervisor','master'])
def portaria_entrada():
    d = request.form
    eid = current_empresa() or d.get('empresa_id')
    pid = current_posto() or d.get('posto_id')
    conn = get_db()
    conn.execute("""INSERT INTO visitantes (empresa_id,posto_id,nome,documento,empresa_origem,destino,placa_veiculo,motivo,entrada,operador_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (eid, pid, d['nome'], d.get('documento',''), d.get('empresa_origem',''),
         d.get('destino',''), d.get('placa_veiculo',''), d.get('motivo',''),
         datetime.now().isoformat(), session['user_id']))
    conn.commit(); conn.close()
    flash('Entrada registrada!', 'success')
    return redirect(url_for('portaria'))

@app.route('/portaria/saida/<int:vid>', methods=['POST'])
@login_required(['portaria','supervisor','master'])
def portaria_saida(vid):
    conn = get_db()
    conn.execute("UPDATE visitantes SET saida=? WHERE id=?", (datetime.now().isoformat(), vid))
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'hora': datetime.now().strftime('%H:%M')})

@app.route('/portaria/historico')
@login_required(['portaria','supervisor','master'])
def portaria_historico():
    conn = get_db()
    eid = current_empresa()
    pid = current_posto()
    cfg = get_empresa_config(eid)
    data = request.args.get('data', date.today().isoformat())
    busca = request.args.get('busca','')

    filters = ["DATE(v.entrada)=?"]
    vals = [data]
    if eid: filters.append("v.empresa_id=?"); vals.append(eid)
    if pid: filters.append("v.posto_id=?"); vals.append(pid)
    if busca: filters.append("(v.nome LIKE ? OR v.documento LIKE ? OR v.placa_veiculo LIKE ?)"); vals += [f'%{busca}%']*3

    registros = conn.execute(
        f"SELECT v.*, p.nome as posto_nome FROM visitantes v LEFT JOIN postos p ON p.id=v.posto_id WHERE {' AND '.join(filters)} ORDER BY v.entrada DESC",
        vals
    ).fetchall()
    conn.close()
    return render_template('portaria_historico.html', registros=registros, cfg=cfg, data=data, busca=busca)

# ─── FROTA ────────────────────────────────────────────────────────────────────

@app.route('/frota')
@login_required(['portaria','supervisor','master'])
def frota():
    conn = get_db()
    eid = current_empresa()
    cfg = get_empresa_config(eid)
    eid_p = eid or 0

    veiculos = conn.execute(
        "SELECT v.*, p.nome as posto_nome FROM veiculos v LEFT JOIN postos p ON p.id=v.posto_id WHERE v.ativo=1 AND (v.empresa_id=? OR ?=0)",
        (eid_p, eid_p)
    ).fetchall()
    motoristas = conn.execute(
        "SELECT * FROM vigilantes WHERE habilitado_frota=1 AND ativo=1 AND (empresa_id=? OR ?=0)",
        (eid_p, eid_p)
    ).fetchall()
    registros = conn.execute("""
        SELECT rf.*, v.placa, v.modelo, vig.nome as motorista
        FROM registros_frota rf
        JOIN veiculos v ON v.id=rf.veiculo_id
        JOIN vigilantes vig ON vig.id=rf.motorista_id
        WHERE (rf.empresa_id=? OR ?=0)
        ORDER BY rf.saida DESC LIMIT 50
    """, (eid_p, eid_p)).fetchall()
    conn.close()
    return render_template('frota.html', veiculos=veiculos, motoristas=motoristas, registros=registros, cfg=cfg)

@app.route('/frota/saida', methods=['POST'])
@login_required(['portaria','supervisor','master'])
def frota_saida():
    d = request.form
    eid = current_empresa()
    checklist = {k.replace('ch_',''):v for k,v in d.items() if k.startswith('ch_')}
    conn = get_db()
    conn.execute("UPDATE veiculos SET km_atual=? WHERE id=?", (d['km_saida'], d['veiculo_id']))
    conn.execute("""INSERT INTO registros_frota (empresa_id,veiculo_id,motorista_id,destino,motivo,km_saida,saida,checklist_saida,operador_id)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (eid, d['veiculo_id'], d['motorista_id'], d['destino'], d.get('motivo',''),
         d['km_saida'], datetime.now().isoformat(), json.dumps(checklist), session['user_id']))
    conn.commit(); conn.close()
    flash('Saída registrada!', 'success')
    return redirect(url_for('frota'))

@app.route('/frota/chegada/<int:rid>', methods=['POST'])
@login_required(['portaria','supervisor','master'])
def frota_chegada(rid):
    d = request.form
    checklist = {k.replace('ch_',''):v for k,v in d.items() if k.startswith('ch_')}
    conn = get_db()
    reg = conn.execute("SELECT veiculo_id FROM registros_frota WHERE id=?", (rid,)).fetchone()
    conn.execute("UPDATE veiculos SET km_atual=? WHERE id=?", (d['km_chegada'], reg['veiculo_id']))
    conn.execute("UPDATE registros_frota SET km_chegada=?,chegada=?,checklist_chegada=?,obs=? WHERE id=?",
        (d['km_chegada'], datetime.now().isoformat(), json.dumps(checklist), d.get('obs',''), rid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── SEGURANÇA / VIGILANTES ───────────────────────────────────────────────────

@app.route('/seguranca')
@login_required(['seguranca','supervisor','master'])
def seguranca():
    conn = get_db()
    eid = current_empresa()
    pid = current_posto()
    cfg = get_empresa_config(eid)
    hoje = date.today().isoformat()
    hoje_30 = (date.today()+timedelta(days=30)).isoformat()
    hoje_60 = (date.today()+timedelta(days=60)).isoformat()

    eid_p = eid or 0
    pid_p = pid or 0

    postos = conn.execute("SELECT * FROM postos WHERE empresa_id=? AND ativo=1",(eid,)).fetchall() if eid else []
    vigilantes = conn.execute(
        "SELECT vig.*, p.nome as posto_nome FROM vigilantes vig LEFT JOIN postos p ON p.id=vig.posto_id WHERE vig.ativo=1 AND (vig.empresa_id=? OR ?=0) AND (vig.posto_id=? OR ?=0) ORDER BY vig.nome",
        (eid_p, eid_p, pid_p, pid_p)
    ).fetchall()
    aso_vencidos = conn.execute("SELECT * FROM vigilantes WHERE aso_validade < ? AND ativo=1 AND (empresa_id=? OR ?=0)", (hoje, eid_p, eid_p)).fetchall()
    aso_vencendo = conn.execute("SELECT * FROM vigilantes WHERE aso_validade BETWEEN ? AND ? AND ativo=1 AND (empresa_id=? OR ?=0)", (hoje, hoje_30, eid_p, eid_p)).fetchall()
    porte_vencendo = conn.execute("SELECT * FROM vigilantes WHERE porte_arma=1 AND porte_validade <= ? AND ativo=1 AND (empresa_id=? OR ?=0)", (hoje_60, eid_p, eid_p)).fetchall()
    cnh_vencendo = conn.execute("SELECT * FROM vigilantes WHERE cnh_validade <= ? AND habilitado_frota=1 AND ativo=1 AND (empresa_id=? OR ?=0)", (hoje_60, eid_p, eid_p)).fetchall()

    conn.close()
    return render_template('seguranca.html', vigilantes=vigilantes, cfg=cfg, postos=postos,
                           aso_vencidos=aso_vencidos, aso_vencendo=aso_vencendo,
                           porte_vencendo=porte_vencendo, cnh_vencendo=cnh_vencendo,
                           today=hoje, today_30=hoje_30)

@app.route('/seguranca/vigilante/add', methods=['POST'])
@login_required(['seguranca','supervisor','master'])
def add_vigilante():
    d = request.form
    nrs = ','.join(request.form.getlist('nrs'))
    eid = current_empresa()
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO vigilantes
        (empresa_id,posto_id,nome,matricula,cpf,cargo,cnh,cnh_validade,habilitado_frota,
         curso_defensiva,data_curso_defensiva,aso_validade,curso_vigilante,porte_arma,porte_validade,nrs)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, d.get('posto_id') or None, d['nome'], d['matricula'], d.get('cpf',''), d.get('cargo','Vigilante'),
         d.get('cnh') or None, d.get('cnh_validade') or None,
         1 if d.get('habilitado_frota') else 0, 1 if d.get('curso_defensiva') else 0,
         d.get('data_curso_defensiva') or None, d.get('aso_validade') or None,
         d.get('curso_vigilante') or None, 1 if d.get('porte_arma') else 0,
         d.get('porte_validade') or None, nrs))
    conn.commit(); conn.close()
    flash('Vigilante salvo!', 'success')
    return redirect(url_for('seguranca'))

@app.route('/seguranca/vigilante/<int:vid>')
@login_required(['seguranca','supervisor','master'])
def get_vigilante(vid):
    conn = get_db()
    v = conn.execute("SELECT * FROM vigilantes WHERE id=?", (vid,)).fetchone()
    conn.close()
    return jsonify(dict(v)) if v else ('', 404)

# ─── MASTER / ADMIN ───────────────────────────────────────────────────────────

@app.route('/master')
@login_required(['master'])
def master_painel():
    conn = get_db()
    empresas = conn.execute("SELECT e.*, COUNT(DISTINCT p.id) as n_postos, COUNT(DISTINCT u.id) as n_users FROM empresas e LEFT JOIN postos p ON p.empresa_id=e.id LEFT JOIN usuarios u ON u.empresa_id=e.id GROUP BY e.id").fetchall()
    conn.close()
    return render_template('master.html', empresas=empresas, cfg={'tema':'dark','cor_primaria':'#3b82f6'})

@app.route('/master/empresa/add', methods=['POST'])
@login_required(['master'])
def add_empresa():
    d = request.form
    conn = get_db()
    conn.execute("INSERT INTO empresas (nome,cnpj,tema,cor_primaria,plano) VALUES (?,?,?,?,?)",
        (d['nome'], d.get('cnpj',''), d.get('tema','dark'), d.get('cor_primaria','#3b82f6'), d.get('plano','basic')))
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Criar supervisor padrão
    if d.get('login_supervisor'):
        senha = hashlib.sha256(d['senha_supervisor'].encode()).hexdigest()
        conn.execute("INSERT INTO usuarios (empresa_id,nome,login,senha,perfil) VALUES (?,?,?,?,?)",
            (eid, d['nome_supervisor'], d['login_supervisor'], senha, 'supervisor'))
    conn.commit(); conn.close()
    flash('Empresa criada!', 'success')
    return redirect(url_for('master_painel'))

@app.route('/master/empresa/<int:eid>/config', methods=['POST'])
@login_required(['master','supervisor'])
def config_empresa(eid):
    d = request.form
    conn = get_db()
    conn.execute("UPDATE empresas SET tema=?,cor_primaria=? WHERE id=?",
        (d['tema'], d['cor_primaria'], eid))
    conn.commit(); conn.close()
    flash('Configurações salvas!', 'success')
    return redirect(request.referrer or url_for('dashboard'))

# ─── SUPERVISOR ───────────────────────────────────────────────────────────────

@app.route('/supervisor')
@login_required(['supervisor','master'])
def supervisor():
    eid = current_empresa()
    cfg = get_empresa_config(eid)
    conn = get_db()
    hoje = date.today().isoformat()
    postos = conn.execute("SELECT * FROM postos WHERE empresa_id=? AND ativo=1", (eid,)).fetchall()

    resumo = []
    for p in postos:
        pid = p['id']
        resumo.append({
            'posto': dict(p),
            'dentro': conn.execute("SELECT COUNT(*) FROM visitantes WHERE posto_id=? AND saida IS NULL AND entrada IS NOT NULL",(pid,)).fetchone()[0],
            'hoje': conn.execute("SELECT COUNT(*) FROM visitantes WHERE posto_id=? AND DATE(entrada)=?",(pid,hoje)).fetchone()[0],
            'veiculos_fora': conn.execute("SELECT COUNT(*) FROM registros_frota rf JOIN veiculos v ON v.id=rf.veiculo_id WHERE v.posto_id=? AND rf.chegada IS NULL AND rf.saida IS NOT NULL",(pid,)).fetchone()[0],
            'vigilantes': conn.execute("SELECT COUNT(*) FROM vigilantes WHERE posto_id=? AND ativo=1",(pid,)).fetchone()[0],
        })

    aso_critico = conn.execute(
        "SELECT * FROM vigilantes WHERE aso_validade <= date('now','+30 days') AND empresa_id=? AND ativo=1 ORDER BY aso_validade", (eid,)
    ).fetchall()
    porte_critico = conn.execute(
        "SELECT * FROM vigilantes WHERE porte_arma=1 AND porte_validade <= date('now','+60 days') AND empresa_id=? AND ativo=1", (eid,)
    ).fetchall()

    conn.close()
    return render_template('supervisor.html', resumo=resumo, cfg=cfg,
                           aso_critico=aso_critico, porte_critico=porte_critico)

# ─── API ──────────────────────────────────────────────────────────────────────

@app.route('/api/stats')
@login_required()
def api_stats():
    conn = get_db()
    eid = current_empresa()
    hoje = date.today().isoformat()
    e_f = "AND empresa_id=?" if eid else ""
    vals = (eid,) if eid else ()
    data = {
        'visitantes_dentro': conn.execute(f"SELECT COUNT(*) FROM visitantes WHERE saida IS NULL AND entrada IS NOT NULL {e_f}", vals).fetchone()[0],
        'visitantes_hoje': conn.execute(f"SELECT COUNT(*) FROM visitantes WHERE DATE(entrada)=? {e_f}", (hoje,*vals)).fetchone()[0],
        'veiculos_fora': conn.execute(f"SELECT COUNT(*) FROM registros_frota WHERE chegada IS NULL AND saida IS NOT NULL {e_f}", vals).fetchone()[0],
    }
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
