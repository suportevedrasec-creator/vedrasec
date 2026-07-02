from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f'<Usuario {self.email}>'


class Devedor(db.Model):
    __tablename__ = 'devedores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cpf_cnpj = db.Column(db.String(20), index=True)
    grupo = db.Column(db.String(100))
    regional = db.Column(db.String(100))
    pa = db.Column(db.String(100))
    data_ultima_atualizacao = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contratos = db.relationship('Contrato', back_populates='devedor', lazy='dynamic',
                                cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'cpf_cnpj': self.cpf_cnpj,
            'grupo': self.grupo,
            'regional': self.regional,
            'pa': self.pa,
            'data_ultima_atualizacao': self.data_ultima_atualizacao.isoformat() if self.data_ultima_atualizacao else None,
            'total_contratos': self.contratos.count(),
        }

    def __repr__(self):
        return f'<Devedor {self.nome}>'


class Contrato(db.Model):
    __tablename__ = 'contratos'
    id = db.Column(db.Integer, primary_key=True)
    devedor_id = db.Column(db.Integer, db.ForeignKey('devedores.id'), nullable=False)
    numero_contrato = db.Column(db.String(50), index=True)
    numero_cliente = db.Column(db.String(50))

    # Valores financeiros
    valor_contratado = db.Column(db.Numeric(15, 2))
    valor_prejuizo = db.Column(db.Numeric(15, 2))
    valor_pago_sec = db.Column(db.Numeric(15, 2))

    # Data base para cálculo
    data_base = db.Column(db.Date)
    indice_1pct = db.Column(db.Numeric(10, 6))
    indice_final = db.Column(db.Numeric(10, 6))

    # Valores corrigidos (simples)
    valor_corrigido_ipca = db.Column(db.Numeric(15, 2))
    juros_mora_simples = db.Column(db.Numeric(15, 2))
    honorarios_simples = db.Column(db.Numeric(15, 2))
    valor_atualizado_simples = db.Column(db.Numeric(15, 2))

    # Valores corrigidos TJSP / Lei 14.905/2024
    valor_corrigido_tjsp = db.Column(db.Numeric(15, 2))
    juros_mora_tjsp_ate_ago2024 = db.Column(db.Numeric(15, 2))
    juros_mora_tjsp_apos_ago2024 = db.Column(db.Numeric(15, 2))
    juros_mora_total_lei14905 = db.Column(db.Numeric(15, 2))
    honorarios_tjsp = db.Column(db.Numeric(15, 2))
    valor_atualizado_lei14905 = db.Column(db.Numeric(15, 2))

    # Honra de avais
    honra_avais_credito = db.Column(db.Numeric(15, 2))

    # Detalhes do contrato
    subdivisao = db.Column(db.String(100))
    modalidade_bacen = db.Column(db.String(100))
    modalidade = db.Column(db.String(100))
    data_liberacao = db.Column(db.Date)
    data_vencimento = db.Column(db.Date)
    data_transf_prejuizo = db.Column(db.Date)

    # Garantias
    garantia_real = db.Column(db.String(200))
    garantia_pessoal = db.Column(db.String(200))
    descricao_garantia = db.Column(db.Text)
    capital_social = db.Column(db.Numeric(15, 2))
    capital_penhora_judicial = db.Column(db.Numeric(15, 2))

    # Cobrança
    grupo_cobranca = db.Column(db.String(100))
    devedor_negativado = db.Column(db.Boolean, default=False)

    # Status
    na_esteira = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    devedor = db.relationship('Devedor', back_populates='contratos')
    processo = db.relationship('Processo', back_populates='contrato', uselist=False,
                               cascade='all, delete-orphan')
    acordo = db.relationship('Acordo', back_populates='contrato', uselist=False,
                             cascade='all, delete-orphan')

    def valor_principal(self):
        return float(self.valor_prejuizo or 0) - float(self.valor_pago_sec or 0)

    def to_dict(self):
        return {
            'id': self.id,
            'devedor_id': self.devedor_id,
            'devedor_nome': self.devedor.nome if self.devedor else None,
            # Identificação
            'numero_contrato': self.numero_contrato,
            'numero_cliente': self.numero_cliente,
            'modalidade_bacen': self.modalidade_bacen,
            'modalidade': self.modalidade,
            'subdivisao': self.subdivisao,
            'grupo_cobranca': self.grupo_cobranca,
            # Valores financeiros
            'valor_contratado': float(self.valor_contratado) if self.valor_contratado else None,
            'valor_prejuizo': float(self.valor_prejuizo) if self.valor_prejuizo else None,
            'valor_pago_sec': float(self.valor_pago_sec) if self.valor_pago_sec else None,
            # Valores atualizados (simples)
            'data_base': self.data_base.isoformat() if self.data_base else None,
            'indice_1pct': float(self.indice_1pct) if self.indice_1pct else None,
            'indice_final': float(self.indice_final) if self.indice_final else None,
            'valor_corrigido_ipca': float(self.valor_corrigido_ipca) if self.valor_corrigido_ipca else None,
            'juros_mora_simples': float(self.juros_mora_simples) if self.juros_mora_simples else None,
            'honorarios_simples': float(self.honorarios_simples) if self.honorarios_simples else None,
            'valor_atualizado_simples': float(self.valor_atualizado_simples) if self.valor_atualizado_simples else None,
            # Valores TJSP / Lei 14.905
            'valor_corrigido_tjsp': float(self.valor_corrigido_tjsp) if self.valor_corrigido_tjsp else None,
            'juros_mora_tjsp_ate_ago2024': float(self.juros_mora_tjsp_ate_ago2024) if self.juros_mora_tjsp_ate_ago2024 else None,
            'juros_mora_tjsp_apos_ago2024': float(self.juros_mora_tjsp_apos_ago2024) if self.juros_mora_tjsp_apos_ago2024 else None,
            'juros_mora_total_lei14905': float(self.juros_mora_total_lei14905) if self.juros_mora_total_lei14905 else None,
            'honorarios_tjsp': float(self.honorarios_tjsp) if self.honorarios_tjsp else None,
            'valor_atualizado_lei14905': float(self.valor_atualizado_lei14905) if self.valor_atualizado_lei14905 else None,
            # Datas
            'data_liberacao': self.data_liberacao.isoformat() if self.data_liberacao else None,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'data_transf_prejuizo': self.data_transf_prejuizo.isoformat() if self.data_transf_prejuizo else None,
            # Garantias
            'garantia_real': self.garantia_real,
            'garantia_pessoal': self.garantia_pessoal,
            'descricao_garantia': self.descricao_garantia,
            'capital_social': float(self.capital_social) if self.capital_social else None,
            'capital_penhora_judicial': float(self.capital_penhora_judicial) if self.capital_penhora_judicial else None,
            'honra_avais_credito': float(self.honra_avais_credito) if self.honra_avais_credito else None,
            # Cobrança
            'devedor_negativado': self.devedor_negativado,
            'na_esteira': self.na_esteira,
        }

    def __repr__(self):
        return f'<Contrato {self.numero_contrato}>'


class Processo(db.Model):
    __tablename__ = 'processos'
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos.id'), nullable=True)
    contrato_referencia = db.Column(db.String(50))  # nº do contrato digitado quando não há vínculo
    numero_processo = db.Column(db.String(50), index=True)
    formalizacao_cessao_autos = db.Column(db.String(100))
    andamentos = db.Column(db.Text)
    detalhamento = db.Column(db.Text)
    providencia = db.Column(db.Text)
    status = db.Column(db.String(100))
    data_movimentacao = db.Column(db.Date)
    provisao_pagamentos = db.Column(db.Numeric(15, 2))
    custos_processo = db.Column(db.Numeric(15, 2))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contrato = db.relationship('Contrato', back_populates='processo')

    def to_dict(self):
        return {
            'id': self.id,
            'contrato_id': self.contrato_id,
            'contrato_referencia': self.contrato_referencia,
            'numero_processo': self.numero_processo,
            'formalizacao_cessao_autos': self.formalizacao_cessao_autos,
            'andamentos': self.andamentos,
            'detalhamento': self.detalhamento,
            'providencia': self.providencia,
            'status': self.status,
            'data_movimentacao': self.data_movimentacao.isoformat() if self.data_movimentacao else None,
            'provisao_pagamentos': float(self.provisao_pagamentos) if self.provisao_pagamentos else None,
            'custos_processo': float(self.custos_processo) if self.custos_processo else None,
        }

    def __repr__(self):
        return f'<Processo {self.numero_processo}>'


class Acordo(db.Model):
    __tablename__ = 'acordos'
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos.id'), nullable=False)

    # Proposta
    proposta = db.Column(db.Text)
    comite = db.Column(db.String(200))
    resultado_proposta = db.Column(db.String(100))
    justificativa = db.Column(db.Text)
    origem_acordo = db.Column(db.String(100))
    status_acordo = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))

    # Valores negociados
    divida_confessada = db.Column(db.Numeric(15, 2))
    divida_transacionada = db.Column(db.Numeric(15, 2))
    detalhamento = db.Column(db.Text)
    percentual_recuperacao = db.Column(db.Numeric(5, 2))
    pendencias = db.Column(db.Text)
    bases_acordo = db.Column(db.Text)

    # Forma de pagamento
    forma_pagamento = db.Column(db.String(50))  # à vista / parcelado
    modalidade_pagamento = db.Column(db.String(100))
    status_pagamento = db.Column(db.String(100))

    # Parcelamento
    n_parcelas = db.Column(db.Integer)
    valor_entrada = db.Column(db.Numeric(15, 2))
    valor_parcela = db.Column(db.Numeric(15, 2))
    periodicidade_parcela = db.Column(db.String(50))
    primeira_parcela = db.Column(db.Date)
    ultima_parcela = db.Column(db.Date)
    parcelas_quitadas = db.Column(db.Integer, default=0)

    # Recebimentos
    valor_recebido = db.Column(db.Numeric(15, 2))
    valor_bloqueado_judicialmente = db.Column(db.Numeric(15, 2))
    data_recebimento = db.Column(db.Date)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contrato = db.relationship('Contrato', back_populates='acordo')

    def to_dict(self):
        return {
            'id': self.id,
            'contrato_id': self.contrato_id,
            'devedor_nome': self.contrato.devedor.nome if self.contrato and self.contrato.devedor else None,
            'proposta': self.proposta,
            'resultado_proposta': self.resultado_proposta,
            'origem_acordo': self.origem_acordo,
            'status_acordo': self.status_acordo,
            'responsavel': self.responsavel,
            'divida_confessada': float(self.divida_confessada) if self.divida_confessada else None,
            'divida_transacionada': float(self.divida_transacionada) if self.divida_transacionada else None,
            'percentual_recuperacao': float(self.percentual_recuperacao) if self.percentual_recuperacao else None,
            'forma_pagamento': self.forma_pagamento,
            'status_pagamento': self.status_pagamento,
            'n_parcelas': self.n_parcelas,
            'valor_parcela': float(self.valor_parcela) if self.valor_parcela else None,
            'parcelas_quitadas': self.parcelas_quitadas,
            'valor_recebido': float(self.valor_recebido) if self.valor_recebido else None,
        }

    def __repr__(self):
        return f'<Acordo {self.id} - Contrato {self.contrato_id}>'


class IndiceMonetario(db.Model):
    __tablename__ = 'indices_monetarios'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    mes_ano = db.Column(db.String(10))
    ufesp = db.Column(db.Numeric(10, 6))
    selic = db.Column(db.Numeric(10, 6))
    selic_acumulada_set2024 = db.Column(db.Numeric(12, 8))
    selic_acumulada = db.Column(db.Numeric(12, 8))
    selic_menos_correcao = db.Column(db.Numeric(10, 6))
    jrs_fixos = db.Column(db.Numeric(10, 6))
    inpc = db.Column(db.Numeric(10, 6))
    ipca15 = db.Column(db.Numeric(10, 6))
    inpc_ipca15 = db.Column(db.Numeric(12, 8))
    bacen_serie29541 = db.Column(db.Numeric(12, 8))

    def to_dict(self):
        return {
            'id': self.id,
            'data': self.data.isoformat() if self.data else None,
            'mes_ano': self.mes_ano,
            'ufesp': float(self.ufesp) if self.ufesp else None,
            'selic': float(self.selic) if self.selic else None,
            'selic_acumulada': float(self.selic_acumulada) if self.selic_acumulada else None,
            'inpc': float(self.inpc) if self.inpc else None,
            'ipca15': float(self.ipca15) if self.ipca15 else None,
            'inpc_ipca15': float(self.inpc_ipca15) if self.inpc_ipca15 else None,
            'bacen_serie29541': float(self.bacen_serie29541) if self.bacen_serie29541 else None,
        }

    def __repr__(self):
        return f'<Indice {self.mes_ano}>'
