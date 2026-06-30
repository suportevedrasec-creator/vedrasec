import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_, desc
from datetime import datetime, date
from decimal import Decimal

from models import db, Usuario, Devedor, Contrato, Processo, Acordo, IndiceMonetario

app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vedra-sec-2024-chave-secreta-altere-em-producao')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vedra_sec.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar o sistema.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


# ─── Autenticação ────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()
        if usuario and usuario.check_senha(senha):
            login_user(usuario, remember=request.form.get('lembrar'))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    total_devedores = Devedor.query.count()
    total_contratos = Contrato.query.count()
    contratos_esteira = Contrato.query.filter_by(na_esteira=True).count()

    soma_prejuizo = db.session.query(func.sum(Contrato.valor_prejuizo)).scalar() or 0
    soma_atualizado = db.session.query(func.sum(Contrato.valor_atualizado_simples)).scalar() or 0
    soma_recebido = db.session.query(func.sum(Acordo.valor_recebido)).scalar() or 0

    acordos_andamento = Acordo.query.filter(
        Acordo.status_acordo.in_(['Em Andamento', 'Acordo em Andamento', 'Pagamento em andamento'])
    ).count()

    acordos_quitados = Acordo.query.filter(
        Acordo.status_pagamento.in_(['Quitado', 'Quitada'])
    ).count()

    # Últimos processos atualizados
    processos_recentes = db.session.query(Processo, Contrato, Devedor)\
        .join(Contrato, Processo.contrato_id == Contrato.id)\
        .join(Devedor, Contrato.devedor_id == Devedor.id)\
        .order_by(desc(Processo.atualizado_em)).limit(8).all()

    # Distribuição por grupo de cobrança — serializar para JSON
    grupos_raw = db.session.query(
        Contrato.grupo_cobranca,
        func.count(Contrato.id).label('qtd'),
        func.sum(Contrato.valor_atualizado_simples).label('total')
    ).group_by(Contrato.grupo_cobranca).all()
    grupos = [[r[0] or 'Sem grupo', r[1], float(r[2] or 0)] for r in grupos_raw]

    # Distribuição por status de processo — serializar para JSON
    status_raw = db.session.query(
        Processo.status,
        func.count(Processo.id).label('qtd')
    ).group_by(Processo.status).all()
    status_dist = [[r[0] or 'Sem status', r[1]] for r in status_raw]

    return render_template('dashboard.html',
        total_devedores=total_devedores,
        total_contratos=total_contratos,
        contratos_esteira=contratos_esteira,
        soma_prejuizo=float(soma_prejuizo),
        soma_atualizado=float(soma_atualizado),
        soma_recebido=float(soma_recebido),
        acordos_andamento=acordos_andamento,
        acordos_quitados=acordos_quitados,
        processos_recentes=processos_recentes,
        grupos=grupos,
        status_dist=status_dist,
    )


# ─── Devedores / Cadastros ───────────────────────────────────────────────────

@app.route('/cadastros')
@login_required
def cadastros():
    return render_template('cadastros.html')


@app.route('/api/devedores')
@login_required
def api_devedores():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    busca = request.args.get('q', '').strip()
    regional = request.args.get('regional', '')
    grupo = request.args.get('grupo', '')

    query = Devedor.query

    if busca:
        query = query.filter(or_(
            Devedor.nome.ilike(f'%{busca}%'),
            Devedor.cpf_cnpj.ilike(f'%{busca}%'),
            Devedor.grupo.ilike(f'%{busca}%'),
        ))
    if regional:
        query = query.filter(Devedor.regional.ilike(f'%{regional}%'))
    if grupo:
        query = query.filter(Devedor.grupo.ilike(f'%{grupo}%'))

    paginacao = query.order_by(Devedor.nome).paginate(page=page, per_page=per_page, error_out=False)

    resultado = []
    for d in paginacao.items:
        item = d.to_dict()
        # Somar valores dos contratos
        soma = db.session.query(
            func.sum(Contrato.valor_atualizado_simples)
        ).filter(Contrato.devedor_id == d.id).scalar()
        item['valor_total'] = float(soma) if soma else 0
        resultado.append(item)

    return jsonify({
        'items': resultado,
        'total': paginacao.total,
        'paginas': paginacao.pages,
        'pagina_atual': page,
    })


@app.route('/api/devedores/<int:devedor_id>')
@login_required
def api_devedor_detalhe(devedor_id):
    devedor = Devedor.query.get_or_404(devedor_id)
    contratos = Contrato.query.filter_by(devedor_id=devedor_id).all()
    return jsonify({
        'devedor': devedor.to_dict(),
        'contratos': [c.to_dict() for c in contratos],
    })


@app.route('/api/devedores', methods=['POST'])
@login_required
def api_criar_devedor():
    data = request.get_json()
    devedor = Devedor(
        nome=data.get('nome', '').strip(),
        cpf_cnpj=data.get('cpf_cnpj', '').strip(),
        grupo=data.get('grupo', '').strip(),
        regional=data.get('regional', '').strip(),
        pa=data.get('pa', '').strip(),
        data_ultima_atualizacao=_parse_date(data.get('data_ultima_atualizacao')),
    )
    db.session.add(devedor)
    db.session.commit()
    return jsonify({'id': devedor.id, 'mensagem': 'Devedor criado com sucesso.'}), 201


@app.route('/api/devedores/<int:devedor_id>', methods=['PUT'])
@login_required
def api_atualizar_devedor(devedor_id):
    devedor = Devedor.query.get_or_404(devedor_id)
    data = request.get_json()
    devedor.nome = data.get('nome', devedor.nome).strip()
    devedor.cpf_cnpj = data.get('cpf_cnpj', devedor.cpf_cnpj)
    devedor.grupo = data.get('grupo', devedor.grupo)
    devedor.regional = data.get('regional', devedor.regional)
    devedor.pa = data.get('pa', devedor.pa)
    devedor.data_ultima_atualizacao = _parse_date(data.get('data_ultima_atualizacao')) or devedor.data_ultima_atualizacao
    db.session.commit()
    return jsonify({'mensagem': 'Devedor atualizado com sucesso.'})


@app.route('/api/devedores/<int:devedor_id>', methods=['DELETE'])
@login_required
def api_deletar_devedor(devedor_id):
    devedor = Devedor.query.get_or_404(devedor_id)
    db.session.delete(devedor)
    db.session.commit()
    return jsonify({'mensagem': 'Devedor removido com sucesso.'})


# ─── Contratos ───────────────────────────────────────────────────────────────

@app.route('/api/contratos')
@login_required
def api_contratos():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    devedor_id = request.args.get('devedor_id', type=int)
    busca = request.args.get('q', '').strip()
    na_esteira = request.args.get('na_esteira')

    query = db.session.query(Contrato, Devedor).join(Devedor, Contrato.devedor_id == Devedor.id)

    if devedor_id:
        query = query.filter(Contrato.devedor_id == devedor_id)
    if busca:
        query = query.filter(or_(
            Devedor.nome.ilike(f'%{busca}%'),
            Contrato.numero_contrato.ilike(f'%{busca}%'),
            Devedor.cpf_cnpj.ilike(f'%{busca}%'),
        ))
    if na_esteira == 'true':
        query = query.filter(Contrato.na_esteira == True)
    elif na_esteira == 'false':
        query = query.filter(Contrato.na_esteira == False)

    total = query.count()
    itens = query.order_by(Devedor.nome).offset((page - 1) * per_page).limit(per_page).all()

    resultado = []
    for c, d in itens:
        item = c.to_dict()
        item['devedor_nome'] = d.nome
        item['devedor_cpf_cnpj'] = d.cpf_cnpj
        item['devedor_regional'] = d.regional
        resultado.append(item)

    return jsonify({
        'items': resultado,
        'total': total,
        'paginas': (total + per_page - 1) // per_page,
        'pagina_atual': page,
    })


@app.route('/api/contratos/<int:contrato_id>')
@login_required
def api_contrato_detalhe(contrato_id):
    c = Contrato.query.get_or_404(contrato_id)
    resultado = c.to_dict()
    resultado['devedor'] = c.devedor.to_dict() if c.devedor else None
    resultado['processo'] = c.processo.to_dict() if c.processo else None
    resultado['acordo'] = c.acordo.to_dict() if c.acordo else None
    return jsonify(resultado)


@app.route('/api/contratos', methods=['POST'])
@login_required
def api_criar_contrato():
    data = request.get_json()
    contrato = Contrato(
        devedor_id=data['devedor_id'],
        numero_contrato=data.get('numero_contrato', '').strip(),
        numero_cliente=data.get('numero_cliente', '').strip(),
        valor_contratado=_decimal(data.get('valor_contratado')),
        valor_prejuizo=_decimal(data.get('valor_prejuizo')),
        valor_pago_sec=_decimal(data.get('valor_pago_sec')),
        data_base=_parse_date(data.get('data_base')),
        modalidade_bacen=data.get('modalidade_bacen', '').strip(),
        modalidade=data.get('modalidade', '').strip(),
        subdivisao=data.get('subdivisao', '').strip(),
        data_liberacao=_parse_date(data.get('data_liberacao')),
        data_vencimento=_parse_date(data.get('data_vencimento')),
        data_transf_prejuizo=_parse_date(data.get('data_transf_prejuizo')),
        garantia_real=data.get('garantia_real', '').strip(),
        garantia_pessoal=data.get('garantia_pessoal', '').strip(),
        descricao_garantia=data.get('descricao_garantia', '').strip(),
        capital_social=_decimal(data.get('capital_social')),
        grupo_cobranca=data.get('grupo_cobranca', '').strip(),
        devedor_negativado=bool(data.get('devedor_negativado', False)),
        na_esteira=bool(data.get('na_esteira', False)),
    )
    db.session.add(contrato)
    db.session.commit()
    return jsonify({'id': contrato.id, 'mensagem': 'Contrato criado com sucesso.'}), 201


@app.route('/api/contratos/<int:contrato_id>', methods=['PUT'])
@login_required
def api_atualizar_contrato(contrato_id):
    c = Contrato.query.get_or_404(contrato_id)
    data = request.get_json()
    campos = ['numero_contrato', 'numero_cliente', 'modalidade_bacen', 'modalidade',
              'subdivisao', 'garantia_real', 'garantia_pessoal', 'descricao_garantia',
              'grupo_cobranca']
    for campo in campos:
        if campo in data:
            setattr(c, campo, data[campo].strip() if data[campo] else '')
    decimais = ['valor_contratado', 'valor_prejuizo', 'valor_pago_sec', 'capital_social',
                'valor_corrigido_ipca', 'juros_mora_simples', 'honorarios_simples',
                'valor_atualizado_simples', 'valor_corrigido_tjsp', 'honorarios_tjsp',
                'valor_atualizado_lei14905', 'indice_1pct', 'indice_final']
    for campo in decimais:
        if campo in data:
            setattr(c, campo, _decimal(data[campo]))
    datas = ['data_base', 'data_liberacao', 'data_vencimento', 'data_transf_prejuizo']
    for campo in datas:
        if campo in data:
            setattr(c, campo, _parse_date(data[campo]))
    if 'devedor_negativado' in data:
        c.devedor_negativado = bool(data['devedor_negativado'])
    if 'na_esteira' in data:
        c.na_esteira = bool(data['na_esteira'])
    db.session.commit()
    return jsonify({'mensagem': 'Contrato atualizado com sucesso.'})


# ─── Esteira ─────────────────────────────────────────────────────────────────

@app.route('/esteira')
@login_required
def esteira():
    return render_template('esteira.html')


@app.route('/api/esteira')
@login_required
def api_esteira():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    busca = request.args.get('q', '').strip()
    status = request.args.get('status', '')

    query = db.session.query(Processo, Contrato, Devedor)\
        .join(Contrato, Processo.contrato_id == Contrato.id)\
        .join(Devedor, Contrato.devedor_id == Devedor.id)

    if busca:
        query = query.filter(or_(
            Devedor.nome.ilike(f'%{busca}%'),
            Processo.numero_processo.ilike(f'%{busca}%'),
            Devedor.cpf_cnpj.ilike(f'%{busca}%'),
            Contrato.numero_contrato.ilike(f'%{busca}%'),
        ))
    if status:
        query = query.filter(Processo.status.ilike(f'%{status}%'))

    total = query.count()
    itens = query.order_by(desc(Processo.atualizado_em)).offset((page - 1) * per_page).limit(per_page).all()

    resultado = []
    for p, c, d in itens:
        resultado.append({
            'processo_id': p.id,
            'contrato_id': c.id,
            'devedor_nome': d.nome,
            'devedor_cpf_cnpj': d.cpf_cnpj,
            'devedor_regional': d.regional,
            'numero_contrato': c.numero_contrato,
            'numero_processo': p.numero_processo,
            'valor_atualizado': float(c.valor_atualizado_simples) if c.valor_atualizado_simples else None,
            'valor_atualizado_lei14905': float(c.valor_atualizado_lei14905) if c.valor_atualizado_lei14905 else None,
            'garantia_real': c.garantia_real,
            'grupo_cobranca': c.grupo_cobranca,
            'andamentos': p.andamentos,
            'detalhamento': p.detalhamento,
            'providencia': p.providencia,
            'status': p.status,
            'data_movimentacao': p.data_movimentacao.isoformat() if p.data_movimentacao else None,
            'formalizacao_cessao_autos': p.formalizacao_cessao_autos,
            'provisao_pagamentos': float(p.provisao_pagamentos) if p.provisao_pagamentos else None,
            'tem_acordo': c.acordo is not None,
        })

    return jsonify({
        'items': resultado,
        'total': total,
        'paginas': (total + per_page - 1) // per_page,
        'pagina_atual': page,
    })


@app.route('/api/processos', methods=['POST'])
@login_required
def api_criar_processo():
    data = request.get_json()
    processo = Processo(
        contrato_id=data['contrato_id'],
        numero_processo=data.get('numero_processo', '').strip(),
        formalizacao_cessao_autos=data.get('formalizacao_cessao_autos', '').strip(),
        andamentos=data.get('andamentos', '').strip(),
        detalhamento=data.get('detalhamento', '').strip(),
        providencia=data.get('providencia', '').strip(),
        status=data.get('status', '').strip(),
        data_movimentacao=_parse_date(data.get('data_movimentacao')),
        provisao_pagamentos=_decimal(data.get('provisao_pagamentos')),
        custos_processo=_decimal(data.get('custos_processo')),
    )
    # Marcar contrato na esteira
    contrato = Contrato.query.get(data['contrato_id'])
    if contrato:
        contrato.na_esteira = True
    db.session.add(processo)
    db.session.commit()
    return jsonify({'id': processo.id, 'mensagem': 'Processo cadastrado com sucesso.'}), 201


@app.route('/api/processos/<int:processo_id>', methods=['PUT'])
@login_required
def api_atualizar_processo(processo_id):
    p = Processo.query.get_or_404(processo_id)
    data = request.get_json()
    campos_texto = ['numero_processo', 'formalizacao_cessao_autos', 'andamentos',
                    'detalhamento', 'providencia', 'status']
    for campo in campos_texto:
        if campo in data:
            setattr(p, campo, (data[campo] or '').strip())
    if 'data_movimentacao' in data:
        p.data_movimentacao = _parse_date(data['data_movimentacao'])
    if 'provisao_pagamentos' in data:
        p.provisao_pagamentos = _decimal(data['provisao_pagamentos'])
    if 'custos_processo' in data:
        p.custos_processo = _decimal(data['custos_processo'])
    db.session.commit()
    return jsonify({'mensagem': 'Processo atualizado com sucesso.'})


# ─── Acordos ─────────────────────────────────────────────────────────────────

@app.route('/acordos')
@login_required
def acordos():
    return render_template('acordos.html')


@app.route('/api/acordos')
@login_required
def api_acordos():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    busca = request.args.get('q', '').strip()
    status = request.args.get('status', '')

    query = db.session.query(Acordo, Contrato, Devedor)\
        .join(Contrato, Acordo.contrato_id == Contrato.id)\
        .join(Devedor, Contrato.devedor_id == Devedor.id)

    if busca:
        query = query.filter(or_(
            Devedor.nome.ilike(f'%{busca}%'),
            Devedor.cpf_cnpj.ilike(f'%{busca}%'),
            Contrato.numero_contrato.ilike(f'%{busca}%'),
        ))
    if status:
        query = query.filter(or_(
            Acordo.status_acordo.ilike(f'%{status}%'),
            Acordo.status_pagamento.ilike(f'%{status}%'),
        ))

    total = query.count()
    itens = query.order_by(desc(Acordo.atualizado_em)).offset((page - 1) * per_page).limit(per_page).all()

    resultado = []
    for a, c, d in itens:
        resultado.append({
            'acordo_id': a.id,
            'contrato_id': c.id,
            'devedor_nome': d.nome,
            'devedor_cpf_cnpj': d.cpf_cnpj,
            'numero_contrato': c.numero_contrato,
            'origem_acordo': a.origem_acordo,
            'status_acordo': a.status_acordo,
            'resultado_proposta': a.resultado_proposta,
            'responsavel': a.responsavel,
            'divida_confessada': float(a.divida_confessada) if a.divida_confessada else None,
            'divida_transacionada': float(a.divida_transacionada) if a.divida_transacionada else None,
            'percentual_recuperacao': float(a.percentual_recuperacao) if a.percentual_recuperacao else None,
            'forma_pagamento': a.forma_pagamento,
            'status_pagamento': a.status_pagamento,
            'n_parcelas': a.n_parcelas,
            'parcelas_quitadas': a.parcelas_quitadas,
            'valor_recebido': float(a.valor_recebido) if a.valor_recebido else None,
            'data_recebimento': a.data_recebimento.isoformat() if a.data_recebimento else None,
        })

    return jsonify({
        'items': resultado,
        'total': total,
        'paginas': (total + per_page - 1) // per_page,
        'pagina_atual': page,
    })


@app.route('/api/acordos', methods=['POST'])
@login_required
def api_criar_acordo():
    data = request.get_json()
    acordo = Acordo(
        contrato_id=data['contrato_id'],
        proposta=data.get('proposta', '').strip(),
        comite=data.get('comite', '').strip(),
        resultado_proposta=data.get('resultado_proposta', '').strip(),
        justificativa=data.get('justificativa', '').strip(),
        origem_acordo=data.get('origem_acordo', '').strip(),
        status_acordo=data.get('status_acordo', '').strip(),
        responsavel=data.get('responsavel', '').strip(),
        divida_confessada=_decimal(data.get('divida_confessada')),
        divida_transacionada=_decimal(data.get('divida_transacionada')),
        detalhamento=data.get('detalhamento', '').strip(),
        percentual_recuperacao=_decimal(data.get('percentual_recuperacao')),
        pendencias=data.get('pendencias', '').strip(),
        bases_acordo=data.get('bases_acordo', '').strip(),
        forma_pagamento=data.get('forma_pagamento', '').strip(),
        modalidade_pagamento=data.get('modalidade_pagamento', '').strip(),
        status_pagamento=data.get('status_pagamento', '').strip(),
        n_parcelas=data.get('n_parcelas'),
        valor_entrada=_decimal(data.get('valor_entrada')),
        valor_parcela=_decimal(data.get('valor_parcela')),
        periodicidade_parcela=data.get('periodicidade_parcela', '').strip(),
        primeira_parcela=_parse_date(data.get('primeira_parcela')),
        ultima_parcela=_parse_date(data.get('ultima_parcela')),
        parcelas_quitadas=data.get('parcelas_quitadas', 0),
        valor_recebido=_decimal(data.get('valor_recebido')),
        valor_bloqueado_judicialmente=_decimal(data.get('valor_bloqueado_judicialmente')),
        data_recebimento=_parse_date(data.get('data_recebimento')),
    )
    db.session.add(acordo)
    db.session.commit()
    return jsonify({'id': acordo.id, 'mensagem': 'Acordo registrado com sucesso.'}), 201


@app.route('/api/acordos/<int:acordo_id>', methods=['PUT'])
@login_required
def api_atualizar_acordo(acordo_id):
    a = Acordo.query.get_or_404(acordo_id)
    data = request.get_json()
    campos_texto = ['proposta', 'comite', 'resultado_proposta', 'justificativa',
                    'origem_acordo', 'status_acordo', 'responsavel', 'detalhamento',
                    'pendencias', 'bases_acordo', 'forma_pagamento', 'modalidade_pagamento',
                    'status_pagamento', 'periodicidade_parcela']
    for campo in campos_texto:
        if campo in data:
            setattr(a, campo, (data[campo] or '').strip())
    decimais = ['divida_confessada', 'divida_transacionada', 'percentual_recuperacao',
                'valor_entrada', 'valor_parcela', 'valor_recebido', 'valor_bloqueado_judicialmente']
    for campo in decimais:
        if campo in data:
            setattr(a, campo, _decimal(data[campo]))
    if 'n_parcelas' in data:
        a.n_parcelas = data['n_parcelas']
    if 'parcelas_quitadas' in data:
        a.parcelas_quitadas = data['parcelas_quitadas']
    for campo in ['primeira_parcela', 'ultima_parcela', 'data_recebimento']:
        if campo in data:
            setattr(a, campo, _parse_date(data[campo]))
    db.session.commit()
    return jsonify({'mensagem': 'Acordo atualizado com sucesso.'})


# ─── Índices Monetários ───────────────────────────────────────────────────────

@app.route('/indices')
@login_required
def indices():
    return render_template('indices.html')


@app.route('/api/indices')
@login_required
def api_indices():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)
    ano = request.args.get('ano', type=int)

    query = IndiceMonetario.query
    if ano:
        query = query.filter(
            func.strftime('%Y', IndiceMonetario.data) == str(ano)
        )

    total = query.count()
    itens = query.order_by(desc(IndiceMonetario.data)).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'items': [i.to_dict() for i in itens],
        'total': total,
        'paginas': (total + per_page - 1) // per_page,
        'pagina_atual': page,
    })


@app.route('/api/indices', methods=['POST'])
@login_required
def api_criar_indice():
    data = request.get_json()
    indice = IndiceMonetario(
        data=_parse_date(data['data']),
        mes_ano=data.get('mes_ano', '').strip(),
        ufesp=_decimal(data.get('ufesp')),
        selic=_decimal(data.get('selic')),
        selic_acumulada_set2024=_decimal(data.get('selic_acumulada_set2024')),
        selic_acumulada=_decimal(data.get('selic_acumulada')),
        selic_menos_correcao=_decimal(data.get('selic_menos_correcao')),
        jrs_fixos=_decimal(data.get('jrs_fixos')),
        inpc=_decimal(data.get('inpc')),
        ipca15=_decimal(data.get('ipca15')),
        inpc_ipca15=_decimal(data.get('inpc_ipca15')),
        bacen_serie29541=_decimal(data.get('bacen_serie29541')),
    )
    db.session.add(indice)
    db.session.commit()
    return jsonify({'id': indice.id, 'mensagem': 'Índice cadastrado com sucesso.'}), 201


@app.route('/api/indices/<int:indice_id>', methods=['PUT'])
@login_required
def api_atualizar_indice(indice_id):
    idx = IndiceMonetario.query.get_or_404(indice_id)
    data = request.get_json()
    decimais = ['ufesp', 'selic', 'selic_acumulada_set2024', 'selic_acumulada',
                'selic_menos_correcao', 'jrs_fixos', 'inpc', 'ipca15', 'inpc_ipca15', 'bacen_serie29541']
    for campo in decimais:
        if campo in data:
            setattr(idx, campo, _decimal(data[campo]))
    if 'mes_ano' in data:
        idx.mes_ano = data['mes_ano'].strip()
    db.session.commit()
    return jsonify({'mensagem': 'Índice atualizado com sucesso.'})


# ─── Relatório Diário ─────────────────────────────────────────────────────────

@app.route('/relatorio-diario')
@login_required
def relatorio_diario():
    return render_template('relatorio_diario.html')


@app.route('/api/relatorio-diario')
@login_required
def api_relatorio_diario():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    query = db.session.query(Acordo, Contrato, Devedor)\
        .join(Contrato, Acordo.contrato_id == Contrato.id)\
        .join(Devedor, Contrato.devedor_id == Devedor.id)

    if data_inicio:
        query = query.filter(Acordo.data_recebimento >= _parse_date(data_inicio))
    if data_fim:
        query = query.filter(Acordo.data_recebimento <= _parse_date(data_fim))

    itens = query.order_by(Acordo.data_recebimento).all()

    resultado = []
    for a, c, d in itens:
        resultado.append({
            'data_acordo': a.criado_em.date().isoformat() if a.criado_em else None,
            'origem_acordo': a.origem_acordo,
            'status_acordo': a.status_acordo,
            'status_pagamento': a.status_pagamento,
            'cpf_cnpj': d.cpf_cnpj,
            'devedor_nome': d.nome,
            'grupo': d.grupo,
            'numero_contrato': c.numero_contrato,
            'modalidade': c.modalidade_bacen,
            'garantia_real': c.garantia_real,
            'grupo_cobranca': c.grupo_cobranca,
            'n_parcelas': a.n_parcelas,
            'valor_parcela': float(a.valor_parcela) if a.valor_parcela else None,
            'valor_recebido': float(a.valor_recebido) if a.valor_recebido else None,
            'data_recebimento': a.data_recebimento.isoformat() if a.data_recebimento else None,
            'proposta': a.proposta,
            'observacao': a.detalhamento,
            'valor_amortizado': float(a.valor_recebido) if a.valor_recebido else None,
        })

    return jsonify({'items': resultado})


# ─── Utilitários ─────────────────────────────────────────────────────────────

def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except Exception:
        return None


# ─── Inicialização ────────────────────────────────────────────────────────────

def criar_usuario_padrao():
    if not Usuario.query.filter_by(email='admin@vedrasec.com.br').first():
        admin = Usuario(nome='Administrador', email='admin@vedrasec.com.br')
        admin.set_senha('VedraSec@2024')
        db.session.add(admin)
        db.session.commit()
        print('Sistema iniciado. Login: admin@vedrasec.com.br / VedraSec@2024')


# Inicializar banco ao importar (funciona com gunicorn e execução direta)
with app.app_context():
    db.create_all()
    criar_usuario_padrao()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
