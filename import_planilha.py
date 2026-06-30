"""
Script de importação da planilha "Esteira Créditos Cocred - v15.xlsb"
para o banco de dados do Sistema Vedra SEC.

Uso:
    python import_planilha.py ../path/to/Esteira Créditos Cocred - v15.xlsb

Ou, estando na pasta sistema_vedra:
    python import_planilha.py
    (irá procurar a planilha na pasta pai)
"""

import sys
import os
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

try:
    import pyxlsb
except ImportError:
    print("Instalando pyxlsb...")
    os.system("pip install pyxlsb --break-system-packages")
    import pyxlsb

import pandas as pd
from app import app, db, criar_usuario_padrao
from models import Devedor, Contrato, Processo, Acordo, IndiceMonetario


# ─── Utilitários ─────────────────────────────────────────────────────────────

def _decimal(v):
    if v is None or (isinstance(v, float) and (v != v)):  # NaN check
        return None
    try:
        s = str(v).strip().replace(',', '.').replace('R$', '').replace(' ', '')
        if s in ('', '-', 'nan', 'None'):
            return None
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _date_from_serial(v):
    """Converte serial Excel para date."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v if isinstance(v, date) else v.date()
    try:
        n = float(v)
        if n > 59:
            n -= 1  # Bug Excel 1900
        from datetime import timedelta
        return (datetime(1899, 12, 31) + timedelta(days=int(n))).date()
    except (ValueError, TypeError):
        return None


def _parse_date(v):
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.date() if isinstance(v, datetime) else v
    if isinstance(v, float):
        return _date_from_serial(v)
    s = str(v).strip()
    if not s or s in ('nan', 'None', '0', '0.0'):
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return _date_from_serial(s)
    except Exception:
        return None


def _str(v, maxlen=200):
    if v is None:
        return None
    s = str(v).strip()
    if s in ('nan', 'None', '', '0'):
        return None
    return s[:maxlen] if maxlen else s


def _bool_sim_nao(v):
    if not v:
        return False
    s = str(v).lower().strip()
    return s in ('sim', 'yes', 's', '1', 'true', 'negativado')


# ─── Importar Aba "Completo" ──────────────────────────────────────────────────

def importar_completo(caminho_planilha):
    print("\n📄 Importando aba 'Completo'...")
    rows = []
    with pyxlsb.open_workbook(caminho_planilha) as wb:
        with wb.get_sheet('Completo') as sheet:
            for i, row in enumerate(sheet.rows()):
                rows.append([item.v for item in row])

    if not rows:
        print("  Nenhum dado encontrado.")
        return

    # Linha 0 = títulos de seção (row mergeada), linha 1 = cabeçalhos reais
    headers = [str(h or '').strip() for h in rows[1]]
    data_rows = rows[2:]

    # Mapeamento de colunas (flexível - busca por nome)
    def col(name_patterns):
        for pat in name_patterns:
            for i, h in enumerate(headers):
                if pat.lower() in h.lower():
                    return i
        return None

    c = {
        'data_atualizacao': col(['DATA DA ÚLTIMA','ATUALIZAÇÃO']),
        'nome':             col(['NOME DO DEVEDOR','NOME COOPERADO']),
        'grupo':            col(['GRUPO']),
        'cpf_cnpj':         col(['CPF / CNPJ','CNPJ/CPF']),
        'num_cliente':      col(['Nº Cliente','CLIENTE']),
        'regional':         col(['REGIONAL']),
        'pa':               col(['PA']),
        'contrato':         col(['Contrato']),
        'vl_contratado':    col(['Valor Contratado']),
        'vl_prejuizo':      col(['Valor Prejuizo','Valor Prejuízo']),
        'vl_pago_sec':      col(['Valor PAGO SEC']),
        'data_base':        col(['Data-Base','DATA-BASE']),
        'ind_1pct':         col(['Índice Atualização 1%','1%']),
        'ind_final':        col(['Índice Final']),
        'vl_corr_ipca':     col(['Valor Corrigido (IPCA)']) ,
        'juros_mora':       col(['Juros de Mora (1%']),
        'honorarios':       col(['Honorários (10%)']),
        'vl_atualizado':    col(['Valor Atualizado (Simples)']),
        'vl_corr_tjsp':     col(['Valor Corrigido (IPCA) — TJSP','Corrigido (IPCA) — TJSP']),
        'juros_tjsp_ate':   col(['Até 29/08']),
        'juros_tjsp_apos':  col(['A partir de 30/08']),
        'juros_lei14905':   col(['Lei 14.905']),
        'honor_tjsp':       col(['Honorários (10%) — TJSP']),
        'vl_lei14905':      col(['Valor Atualizado (Lei 14.905']),
        'subdivisao':       col(['Subdivisão']),
        'mod_bacen':        col(['Modalidade Bacen']),
        'modalidade':       col(['Modalidade']) ,
        'dt_liberacao':     col(['Data Liberação']),
        'dt_vencimento':    col(['Data Vencimento']),
        'dt_transf':        col(['Data Transf']),
        'garantia_real':    col(['Garantia Real']),
        'garantia_pessoal': col(['Garantia Pessoal']),
        'desc_garantia':    col(['Descrição da Garantia']),
        'capital_social':   col(['Capital Social']),
        'capital_penhora':  col(['CAPITAL EM PENHORA']),
        'grupo_cobranca':   col(['Grupo de cobrança']),
        'num_processo':     col(['Número do Processo','Nº Processo']),
        'formalizacao':     col(['Formalização da Cessão']),
        'andamentos':       col(['Andamentos']),
        'detalhamento':     col(['Detalhamento']),
        'providencia':      col(['Providência']),
        'status':           col(['Status']),
        'dt_movimentacao':  col(['Data da Movimentação','Data']),
        'provisao':         col(['Provisão de Pagamentos']),
        'proposta':         col(['Propostas de Acordo']),
        'comite':           col(['Comitê','COMITÊ']),
        'resultado':        col(['Resultado da Proposta','RESULTADO PROPOSTA']),
        'justificativa':    col(['Justificativa','JUSTIFICATIVA']),
        'origem_acordo':    col(['Origem do Acordo','Acordo ORIGEM']),
        'status_acordo':    col(['Status do Acordo','Acordo em Andamento']),
        'responsavel':      col(['Responsável']),
        'div_confessada':   col(['Dívida Confessada']),
        'div_transacionada':col(['Dívida Transacionada']),
        'pct_recuperacao':  col(['Percentual a ser recuperado']),
        'pendencias':       col(['Pendências']),
        'bases_acordo':     col(['Bases do Acordo']),
        'forma_pgto':       col(['Forma de Pagamento']),
        'mod_pgto':         col(['Modalidade do Pagamento']),
        'status_pgto':      col(['Status do Pagamento']),
        'negativado':       col(['Devedor Negativado']),
        'n_parcelas':       col(['Quantidade de Parcelas','N. PARCELAS']),
        'vl_entrada':       col(['Valor da Entrada','VALOR ENTRADA']),
        'vl_parcela':       col(['Valor da Parcela','VALOR DA PARCELA']),
        'periodicidade':    col(['Periodicidade da Parcela','PERIODICIDADE PARCELA']),
        'primeira_parcela': col(['Primeira Parcela','PRIMEIRA PARCELA']),
        'ultima_parcela':   col(['Última Parcela','ÚLTIMA PARCELA']),
        'parc_quitadas':    col(['Parcelas Quitadas','PARCELAS QUITADAS']),
        'vl_recebido':      col(['Valor Recebido Acordo','VALOR RECEBIDO ACORDO']),
        'vl_bloqueado':     col(['Valor Bloqueado','VALOR BLOQUEADO']),
        'dt_recebimento':   col(['Data do Recebimento','DATA DO RECEBIMENTO']),
    }

    def get(row, key):
        idx = c.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    importados = 0
    ignorados = 0

    for i, row in enumerate(data_rows):
        if not any(row):
            continue

        nome = _str(get(row, 'nome'), 200)
        if not nome:
            ignorados += 1
            continue

        # ── Devedor ──────────────────────────────────────────────────────────
        cpf_cnpj = _str(get(row, 'cpf_cnpj'), 20)
        devedor = None

        if cpf_cnpj:
            devedor = Devedor.query.filter_by(cpf_cnpj=cpf_cnpj).first()

        if not devedor:
            devedor = Devedor.query.filter_by(nome=nome).first()

        if not devedor:
            devedor = Devedor(
                nome=nome,
                cpf_cnpj=cpf_cnpj,
                grupo=_str(get(row, 'grupo'), 100),
                regional=_str(get(row, 'regional'), 100),
                pa=_str(get(row, 'pa'), 100),
                data_ultima_atualizacao=_parse_date(get(row, 'data_atualizacao')),
            )
            db.session.add(devedor)
            db.session.flush()

        # ── Contrato ─────────────────────────────────────────────────────────
        num_contrato = _str(get(row, 'contrato'), 50)
        tem_processo = bool(_str(get(row, 'num_processo')))
        tem_acordo = bool(_str(get(row, 'proposta')) or _str(get(row, 'resultado')))

        contrato = Contrato(
            devedor_id=devedor.id,
            numero_contrato=num_contrato,
            numero_cliente=_str(get(row, 'num_cliente'), 50),
            valor_contratado=_decimal(get(row, 'vl_contratado')),
            valor_prejuizo=_decimal(get(row, 'vl_prejuizo')),
            valor_pago_sec=_decimal(get(row, 'vl_pago_sec')),
            data_base=_parse_date(get(row, 'data_base')),
            indice_1pct=_decimal(get(row, 'ind_1pct')),
            indice_final=_decimal(get(row, 'ind_final')),
            valor_corrigido_ipca=_decimal(get(row, 'vl_corr_ipca')),
            juros_mora_simples=_decimal(get(row, 'juros_mora')),
            honorarios_simples=_decimal(get(row, 'honorarios')),
            valor_atualizado_simples=_decimal(get(row, 'vl_atualizado')),
            valor_corrigido_tjsp=_decimal(get(row, 'vl_corr_tjsp')),
            juros_mora_tjsp_ate_ago2024=_decimal(get(row, 'juros_tjsp_ate')),
            juros_mora_tjsp_apos_ago2024=_decimal(get(row, 'juros_tjsp_apos')),
            juros_mora_total_lei14905=_decimal(get(row, 'juros_lei14905')),
            honorarios_tjsp=_decimal(get(row, 'honor_tjsp')),
            valor_atualizado_lei14905=_decimal(get(row, 'vl_lei14905')),
            subdivisao=_str(get(row, 'subdivisao'), 100),
            modalidade_bacen=_str(get(row, 'mod_bacen'), 100),
            modalidade=_str(get(row, 'modalidade'), 100),
            data_liberacao=_parse_date(get(row, 'dt_liberacao')),
            data_vencimento=_parse_date(get(row, 'dt_vencimento')),
            data_transf_prejuizo=_parse_date(get(row, 'dt_transf')),
            garantia_real=_str(get(row, 'garantia_real'), 200),
            garantia_pessoal=_str(get(row, 'garantia_pessoal'), 200),
            descricao_garantia=_str(get(row, 'desc_garantia'), None),
            capital_social=_decimal(get(row, 'capital_social')),
            capital_penhora_judicial=_decimal(get(row, 'capital_penhora')),
            grupo_cobranca=_str(get(row, 'grupo_cobranca'), 100),
            devedor_negativado=_bool_sim_nao(get(row, 'negativado')),
            na_esteira=tem_processo,
        )
        db.session.add(contrato)
        db.session.flush()

        # ── Processo ─────────────────────────────────────────────────────────
        if tem_processo or _str(get(row, 'status')):
            processo = Processo(
                contrato_id=contrato.id,
                numero_processo=_str(get(row, 'num_processo'), 50),
                formalizacao_cessao_autos=_str(get(row, 'formalizacao'), 100),
                andamentos=_str(get(row, 'andamentos'), None),
                detalhamento=_str(get(row, 'detalhamento'), None),
                providencia=_str(get(row, 'providencia'), None),
                status=_str(get(row, 'status'), 100),
                data_movimentacao=_parse_date(get(row, 'dt_movimentacao')),
                provisao_pagamentos=_decimal(get(row, 'provisao')),
            )
            db.session.add(processo)

        # ── Acordo ───────────────────────────────────────────────────────────
        if tem_acordo:
            acordo = Acordo(
                contrato_id=contrato.id,
                proposta=_str(get(row, 'proposta'), None),
                comite=_str(get(row, 'comite'), 200),
                resultado_proposta=_str(get(row, 'resultado'), 100),
                justificativa=_str(get(row, 'justificativa'), None),
                origem_acordo=_str(get(row, 'origem_acordo'), 100),
                status_acordo=_str(get(row, 'status_acordo'), 100),
                responsavel=_str(get(row, 'responsavel'), 100),
                divida_confessada=_decimal(get(row, 'div_confessada')),
                divida_transacionada=_decimal(get(row, 'div_transacionada')),
                percentual_recuperacao=_decimal(get(row, 'pct_recuperacao')),
                pendencias=_str(get(row, 'pendencias'), None),
                bases_acordo=_str(get(row, 'bases_acordo'), None),
                forma_pagamento=_str(get(row, 'forma_pgto'), 50),
                modalidade_pagamento=_str(get(row, 'mod_pgto'), 100),
                status_pagamento=_str(get(row, 'status_pgto'), 100),
                n_parcelas=int(get(row, 'n_parcelas') or 0) or None,
                valor_entrada=_decimal(get(row, 'vl_entrada')),
                valor_parcela=_decimal(get(row, 'vl_parcela')),
                periodicidade_parcela=_str(get(row, 'periodicidade'), 50),
                primeira_parcela=_parse_date(get(row, 'primeira_parcela')),
                ultima_parcela=_parse_date(get(row, 'ultima_parcela')),
                parcelas_quitadas=int(get(row, 'parc_quitadas') or 0) or 0,
                valor_recebido=_decimal(get(row, 'vl_recebido')),
                valor_bloqueado_judicialmente=_decimal(get(row, 'vl_bloqueado')),
                data_recebimento=_parse_date(get(row, 'dt_recebimento')),
            )
            db.session.add(acordo)

        importados += 1

        if importados % 50 == 0:
            db.session.commit()
            print(f"  {importados} registros processados...")

    db.session.commit()
    print(f"  ✅ Completo: {importados} registros importados, {ignorados} ignorados.")


# ─── Importar Aba "Índice" ────────────────────────────────────────────────────

def importar_indices(caminho_planilha):
    print("\n📊 Importando aba 'Índice'...")
    rows = []
    with pyxlsb.open_workbook(caminho_planilha) as wb:
        with wb.get_sheet('Índice') as sheet:
            for row in sheet.rows():
                rows.append([item.v for item in row])

    if not rows:
        print("  Nenhum dado encontrado.")
        return

    headers = [str(h or '').strip().upper() for h in rows[0]]

    def col(patterns):
        for p in patterns:
            for i, h in enumerate(headers):
                if p.upper() in h:
                    return i
        return None

    c = {
        'data':             col(['DATA']),
        'mes_ano':          col(['MÊS/ANO','MES/ANO']),
        'ufesp':            col(['UFESP']),
        'selic':            col(['SELIC']) ,
        'selic_ac_set24':   col(['SELIC ACUMULADA (SET']),
        'selic_ac':         col(['SELIC ACUMULADA']),
        'jrs_fixos':        col(['JRS._FIXOS','JRS.FIXOS','JRS FIXOS']),
        'inpc':             col(['INPC']),
        'ipca15':           col(['IPCA-15']),
        'inpc_ipca15':      col(['INPC + IPCA']),
        'bacen':            col(['BACEN']),
    }

    importados = 0
    for row in rows[1:]:
        if not any(row):
            continue
        data_val = row[c['data']] if c['data'] is not None and c['data'] < len(row) else None
        data = _parse_date(data_val)
        if not data:
            continue

        # Verificar se já existe
        existente = IndiceMonetario.query.filter_by(data=data).first()
        if existente:
            continue

        def rv(key):
            idx = c.get(key)
            return row[idx] if idx is not None and idx < len(row) else None

        # Processar SELIC (pode ter duas colunas com nome similar)
        selic_val = rv('selic')
        if c.get('selic') is not None and c.get('selic_ac_set24') == c.get('selic'):
            # mesma coluna, pegar próxima
            pass

        idx = IndiceMonetario(
            data=data,
            mes_ano=_str(rv('mes_ano')),
            ufesp=_decimal(rv('ufesp')),
            selic=_decimal(rv('selic')),
            selic_acumulada_set2024=_decimal(rv('selic_ac_set24')),
            selic_acumulada=_decimal(rv('selic_ac')),
            jrs_fixos=_decimal(rv('jrs_fixos')),
            inpc=_decimal(rv('inpc')),
            ipca15=_decimal(rv('ipca15')),
            inpc_ipca15=_decimal(rv('inpc_ipca15')),
            bacen_serie29541=_decimal(rv('bacen')),
        )
        db.session.add(idx)
        importados += 1

    db.session.commit()
    print(f"  ✅ Índices: {importados} registros importados.")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Encontrar planilha
    if len(sys.argv) > 1:
        planilha = sys.argv[1]
    else:
        # Procurar na pasta pai
        pasta_pai = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidatos = [f for f in os.listdir(pasta_pai) if f.endswith('.xlsb') or f.endswith('.xlsx')]
        if not candidatos:
            print("❌ Nenhuma planilha encontrada. Informe o caminho como argumento.")
            sys.exit(1)
        planilha = os.path.join(pasta_pai, candidatos[0])

    if not os.path.exists(planilha):
        print(f"❌ Arquivo não encontrado: {planilha}")
        sys.exit(1)

    print(f"📂 Planilha: {planilha}")

    with app.app_context():
        db.create_all()
        criar_usuario_padrao()

        total_antes = Devedor.query.count()
        if total_antes > 0:
            resposta = input(f"\n⚠️  Já existem {total_antes} devedores no banco. Importar mesmo assim? (s/N): ")
            if resposta.lower() not in ('s', 'sim', 'y', 'yes'):
                print("Importação cancelada.")
                sys.exit(0)

        print("\n🔄 Iniciando importação...")
        try:
            importar_completo(planilha)
        except Exception as e:
            print(f"  ⚠️  Erro na aba Completo: {e}")
            import traceback; traceback.print_exc()

        try:
            importar_indices(planilha)
        except Exception as e:
            print(f"  ⚠️  Erro na aba Índice: {e}")
            import traceback; traceback.print_exc()

        total_depois = Devedor.query.count()
        total_contratos = Contrato.query.count()
        total_processos = Processo.query.count()
        total_acordos = Acordo.query.count()
        total_indices = IndiceMonetario.query.count()

        print(f"""
✅ Importação concluída!
   Devedores:  {total_depois}
   Contratos:  {total_contratos}
   Processos:  {total_processos}
   Acordos:    {total_acordos}
   Índices:    {total_indices}

🚀 Para iniciar o sistema: python app.py
""")
