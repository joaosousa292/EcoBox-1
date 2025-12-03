from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import IntegrityError
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import json
import io
import base64
import qrcode   # pip install qrcode[pil]
from flask import jsonify

app = Flask(__name__)
app.secret_key = "newtech_secret"

def get_db_connection():
        return mysql.connector.connect(
            host="localhost",
            user="root",
            port="3406",
            password="",   # ajuste aqui se tem senha
            database="ecobox"
        )

@app.route("/sobre")
def sobre():

    # =============== BUSCA DADOS DO USUÁRIO ===============
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    if "usuario_id" in session:
        usuario_id = session["usuario_id"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT nome, email, foto_usuario, horas_online
            FROM cliente
            WHERE id = %s
        """, (usuario_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            usuario = user["nome"]
            email = user["email"]

            # foto normalizada
            if user["foto_usuario"]:
                fotoUsuario = url_for(
                    "static",
                    filename=user["foto_usuario"].replace("static/", "")
                )

            horas_online = user.get("horas_online", 0)

    # =============== RENDERIZA TEMPLATE ===============
    return render_template(
        "sobre.html",
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online
    )


@app.route("/", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        tipo = request.form.get("tipo")
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if tipo == "login":
            # pega o usuário pelo email (não busca pela senha!)
            cursor.execute("SELECT * FROM cliente WHERE email=%s", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.close()
                conn.close()
                flash("❌ E-mail ou senha incorretos!", "erro_login")
                return redirect(url_for("auth"))

            senha_db = user.get("senha") or ""

            # 1) tenta validar como hash
            try:
                if senha_db and check_password_hash(senha_db, senha):
                    # sucesso
                    session["usuario"] = user["nome"]
                    session["usuario_id"] = user["id"]
                    session["tipo"] = user.get("tipo")
                    flash(f"👋 Bem-vindo, {user['nome']}!", "sucesso")
                    cursor.close()
                    conn.close()
                    return redirect(url_for("site"))
            except Exception:
                # se check_password_hash levantar erro por formato, cairemos para a comparação direta
                pass

            # 2) fallback: se o DB contém senha em texto puro (legacy), compare direto
            if senha_db == senha:
                # re-hash automático para migrar a conta para hash (melhora segurança)
                try:
                    novo_hash = generate_password_hash(senha)
                    upd = conn.cursor()
                    upd.execute("UPDATE cliente SET senha=%s WHERE id=%s", (novo_hash, user["id"]))
                    conn.commit()
                    upd.close()
                except Exception as e:
                    print("Erro ao migrar senha do usuário para hash:", e)

                session["usuario"] = user["nome"]
                session["usuario_id"] = user["id"]
                session["tipo"] = user.get("tipo")
                flash(f"👋 Bem-vindo, {user['nome']}!", "sucesso")
                cursor.close()
                conn.close()
                return redirect(url_for("site"))

            # se chegou aqui, senha inválida
            cursor.close()
            conn.close()
            flash("❌ E-mail ou senha incorretos!", "erro_login")
            return redirect(url_for("auth"))

        elif tipo == "cadastro":
            nome = request.form["nome"].strip()
            tipo_usuario = "cliente"

            # hash antes de inserir
            senha_hash = generate_password_hash(senha)

            try:
                cursor.execute(
                    "INSERT INTO cliente (nome, email, senha, tipo) VALUES (%s, %s, %s, %s)",
                    (nome, email, senha_hash, tipo_usuario)
                )
                conn.commit()
                flash("✅ Cadastro realizado com sucesso!", "sucesso_cadastro")
            except IntegrityError:
                flash("⚠️ Este e-mail já está cadastrado!", "erro_cadastro")
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for("auth"))

    return render_template("index.html")


@app.route("/site")
def site():
    if "usuario_id" not in session:
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT nome, email, foto_usuario, horas_online
        FROM cliente
        WHERE id = %s
    """, (usuario_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        session.clear()
        return redirect(url_for("auth"))

    # normaliza foto
    foto = user["foto_usuario"]
    if not foto:
        foto_url = url_for("static", filename="img/padrao_foto.png")
    else:
        foto_url = url_for("static", filename=foto.replace("static/", ""))

    return render_template(
        "site.html",
        usuario=user["nome"],
        email=user["email"],
        fotoUsuario=foto_url,
        horas_online=user.get("horas_online", 0)
    )


@app.route("/visitante")
def visitante():
    return render_template("visitante.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("visitante"))

@app.route("/historia", methods=["GET", "POST"])
def historia():

    # ===================== BUSCA DADOS DO USUÁRIO =====================
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    if "usuario_id" in session:
        usuario_id = session["usuario_id"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT nome, email, foto_usuario, horas_online
            FROM cliente
            WHERE id = %s
        """, (usuario_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            usuario = user["nome"]
            email = user["email"]

            # Corrige caminho da foto
            if user["foto_usuario"]:
                fotoUsuario = url_for(
                    "static",
                    filename=user["foto_usuario"].replace("static/", "")
                )

            horas_online = user.get("horas_online", 0)

    # ===================== PROCESSA POST (FEEDBACK) =====================
    if request.method == "POST":
        feedback = request.form.get("feedback")

        if feedback.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedbacks (mensagem) VALUES (%s)",
                (feedback,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            flash("💬 Obrigado pelo seu feedback!", "sucesso_feedback")
            return redirect(url_for("historia"))

    # ===================== RENDERIZA TEMPLATE =====================
    return render_template(
        "historia.html",
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online
    )


@app.route("/loja")
def loja():
    # ================== VERIFICA LOGIN ==================
    if "usuario_id" not in session:
        flash("Você precisa fazer login primeiro!", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    # ================== BUSCA DADOS DO USUÁRIO ==================
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT nome, email, foto_usuario, horas_online
        FROM cliente
        WHERE id = %s
    """, (usuario_id,))
    user = cursor.fetchone()

    if user:
        usuario = user["nome"]
        email = user["email"]

        # foto do usuário
        if user["foto_usuario"]:
            fotoUsuario = url_for(
                "static",
                filename=user["foto_usuario"].replace("static/", "")
            )

        horas_online = user.get("horas_online", 0)

    # ================== PRODUTOS ==================
    cursor.execute("SELECT * FROM produtos ORDER BY id ASC")
    produtos = cursor.fetchall()

    # ================== CARRINHO DO USUÁRIO ==================
    itens_carrinho = {}

    cursor.execute(
        "SELECT produto_id, quantidade FROM carrinho WHERE usuario_id=%s",
        (usuario_id,)
    )
    rows = cursor.fetchall()
    itens_carrinho = {row["produto_id"]: row["quantidade"] for row in rows}

    cursor.close()
    conn.close()

    # ================== SLIDES ==================
    slides = [
    {"frase": "🔥 Super promoções EcoBox! Aproveite agora!"},
    {"frase": "🌱 Produtos sustentáveis com preço justo!"},
    {"frase": "💚 Frete grátis acima de R$ 129!"},
]

    # ================== RENDERIZA TEMPLATE ==================
    return render_template(
        "loja.html",
        produtos=produtos,
        itens_carrinho=itens_carrinho,
        slides=slides,
        # variáveis do header:
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online
    )

@app.route("/carrinho")
def carrinho():
    # ================== VERIFICA LOGIN ==================
    if "usuario_id" not in session:
        flash("Você precisa fazer login para ver o carrinho!", "erro")
        return redirect(url_for("auth"))
    
    usuario_id = session["usuario_id"]

    # ================== BUSCA DADOS DO USUÁRIO ==================
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT nome, email, foto_usuario, horas_online
        FROM cliente
        WHERE id = %s
    """, (usuario_id,))
    user = cursor.fetchone()

    if user:
        usuario = user["nome"]
        email = user["email"]

        # foto do usuário
        if user["foto_usuario"]:
            fotoUsuario = url_for(
                "static",
                filename=user["foto_usuario"].replace("static/", "")
            )

        horas_online = user.get("horas_online", 0)

    # ================== BUSCA ITENS DO CARRINHO ==================
    cursor.execute("""
        SELECT 
            c.id AS carrinho_id,
            p.id AS produto_id,
            p.nome,
            p.preco,
            p.imagem,
            c.quantidade,
            (p.preco * c.quantidade) AS total_item
        FROM carrinho c
        INNER JOIN produtos p ON c.produto_id = p.id
        WHERE c.usuario_id = %s
    """, (usuario_id,))

    itens = cursor.fetchall()
    total_geral = sum(item["total_item"] for item in itens)

    cursor.close()
    conn.close()

    # ================== RENDERIZA TEMPLATE ==================
    return render_template(
        "carrinho.html",
        itens=itens,
        total_geral=total_geral,

        # Header do usuário
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online
    )


@app.route("/add_carrinho", methods=["POST"])
def add_carrinho():
    if "usuario_id" not in session:
        flash("Você precisa estar logado para adicionar itens ao carrinho!", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]
    produto_id = request.form.get("produto_id")

    try:
        quantidade_solicitada = int(request.form.get("quantidade", 1))
    except (TypeError, ValueError):
        quantidade_solicitada = 1

    if quantidade_solicitada < 1:
        flash("Quantidade inválida.", "erro")
        return redirect(url_for("loja"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1 — Buscar o estoque atual do produto SEMPRE
    cursor.execute("SELECT preco, estoque FROM produtos WHERE id=%s", (produto_id,))
    produto = cursor.fetchone()

    if not produto:
        cursor.close()
        conn.close()
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("loja"))

    estoque_disponivel = produto["estoque"]

    # 2 — Verificar se já existe item no carrinho
    cursor.execute(
        "SELECT id, quantidade FROM carrinho WHERE usuario_id=%s AND produto_id=%s",
        (usuario_id, produto_id)
    )
    item_existente = cursor.fetchone()

    quantidade_ja_no_carrinho = item_existente["quantidade"] if item_existente else 0

    # 3 — Verificar o total desejado
    nova_qtd_total = quantidade_ja_no_carrinho + quantidade_solicitada

    # 4 — Impedir ultrapassar estoque
    if nova_qtd_total > estoque_disponivel:
        restante = estoque_disponivel - quantidade_ja_no_carrinho

        if restante <= 0:
            flash("⚠ Estoque esgotado para este produto.", "erro")
        else:
            flash(f"⚠ Estoque insuficiente. Máximo que você pode adicionar agora: {restante}", "erro")

        cursor.close()
        conn.close()
        flash("Produto adicionado ao carrinho!", "sucesso")
        return redirect(url_for("loja"))

    # 5 — Inserir ou atualizar
    if item_existente:
        cursor.execute(
            "UPDATE carrinho SET quantidade = %s WHERE id = %s",
            (nova_qtd_total, item_existente["id"])
        )
    else:
        cursor.execute(
            "INSERT INTO carrinho (usuario_id, produto_id, quantidade, preco_unitario) VALUES (%s, %s, %s, %s)",
            (usuario_id, produto_id, quantidade_solicitada, produto["preco"])
        )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Produto adicionado ao carrinho! 🛒", "sucesso")
    return redirect(url_for("loja"))


@app.route("/remover_item/<int:id_carrinho>")
def remover_item(id_carrinho):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM carrinho WHERE id=%s", (id_carrinho,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Item removido do carrinho.", "info")
    return redirect(url_for("carrinho"))

@app.route("/atualizar_quantidade", methods=["POST"])
def atualizar_quantidade():
    id_carrinho = request.form.get("id")
    nova_qtd = int(request.form.get("quantidade", 1))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT produto_id FROM carrinho WHERE id=%s", (id_carrinho,))
    item = cursor.fetchone()

    if not item:
        cursor.close()
        conn.close()
        flash("Item não encontrado.", "erro")
        return redirect(url_for("carrinho"))

    produto_id = item["produto_id"]

    cursor.execute("SELECT estoque FROM produtos WHERE id=%s", (produto_id,))
    produto = cursor.fetchone()

    if not produto:
        cursor.close()
        conn.close()
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("carrinho"))

    estoque_disponivel = produto["estoque"]

    if nova_qtd > estoque_disponivel:
        flash(f"⚠ Estoque máximo disponível: {estoque_disponivel}", "erro")
        cursor.close()
        conn.close()
        return redirect(url_for("carrinho"))

    cursor = conn.cursor()
    cursor.execute(
        "UPDATE carrinho SET quantidade=%s WHERE id=%s",
        (nova_qtd, id_carrinho),
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("carrinho"))

@app.route("/produto/<int:produto_id>", methods=["GET", "POST"])
def produto_detalhes(produto_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM produtos WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()  # pega só um produto

    if not produto:
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("loja"))

    if request.method == "POST":
        quantidade = int(request.form.get("quantidade", 1))
        # adicionar ao carrinho aqui
        flash("Produto adicionado ao carrinho!", "sucesso")
        return redirect(url_for("loja"))

    cursor.close()
    conn.close()
    return render_template("produto.html", produto=produto)

@app.route("/atualizar_carrinho_ajax", methods=["POST"])
def atualizar_carrinho_ajax():
    data = request.get_json()
    id_carrinho = data.get("id")
    nova_qtd = data.get("quantidade")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT produto_id FROM carrinho WHERE id=%s", (id_carrinho,))
    item = cursor.fetchone()

    if not item:
        return {"erro": "Item não encontrado."}, 400

    cursor.execute("SELECT estoque, preco FROM produtos WHERE id=%s", (item["produto_id"],))
    produto = cursor.fetchone()

    if not produto:
        return {"erro": "Produto não encontrado."}, 400

    if nova_qtd > produto["estoque"]:
        return {
            "erro": "Estoque insuficiente",
            "max": produto["estoque"]
        }, 400

    cursor.execute(
        "UPDATE carrinho SET quantidade=%s WHERE id=%s",
        (nova_qtd, id_carrinho)
    )
    conn.commit()

    total_item = produto["preco"] * nova_qtd

    cursor.close()
    conn.close()

    return {"sucesso": True, "total_item": total_item}

@app.route("/api/estoque/<int:produto_id>")
def api_estoque(produto_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT estoque FROM produtos WHERE id=%s", (produto_id,))
    produto = cursor.fetchone()

    cursor.close()
    conn.close()

    if produto:
        return {"estoque": produto["estoque"]}
    else:
        return {"erro": "Produto não encontrado"}, 404


@app.route("/api/verificar_estoque", methods=["POST"])
def api_verificar_estoque():
    data = request.get_json()

    produto_id = data.get("produto_id")
    quantidade = data.get("quantidade", 1)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT estoque FROM produtos WHERE id=%s", (produto_id,))
    produto = cursor.fetchone()

    cursor.close()
    conn.close()

    if not produto:
        return {"erro": "Produto não encontrado"}, 404

    estoque = produto["estoque"]

    if quantidade <= estoque:
        return {"ok": True, "estoque": estoque}
    else:
        return {"ok": False, "estoque": estoque, "maximo": estoque}
    
def _crc16_ccitt(data: bytes) -> str:
    """
    CRC-16/CCITT-FALSE (polynomial 0x1021, init 0xFFFF) — retorna hex maiúsculo 4 dígitos.
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) & 0xFFFF) ^ 0x1021
            else:
                crc = (crc << 1) & 0xFFFF
    return format(crc & 0xFFFF, '04X')

def _tag(id_: str, value: str) -> str:
    v = "" if value is None else str(value)
    return f"{id_}{len(v):02}{v}"

def build_pix_payload(key: str, txid: str, amount: str = None, merchant_name: str = "", merchant_city: str = "SÃO PAULO"):
    """
    Gera payload BR Code (EMV) comumente aceito:
    - key: chave PIX (CPF/CNPJ, e-mail, celular ou aleatória)
    - txid: identificador da transação (p.ex. 'pedido-23' ou '0001')
    - amount: string com valor, ex: '123.45' (ponto decimal). Se None -> sem campo de valor (pagador insere).
    - merchant_name: nome fantasia (máx 25)
    - merchant_city: cidade (máx 15)
    Retorna string do payload completo (já com CRC).
    """
    # Campos básicos EMV (formato ID + length(2) + value)
    payload = ""

    # 00 Payload Format Indicator
    payload += _tag("00", "01")

    # 01 Merchant Account Information — aqui usamos GUI + chave (subtags)
    # subtag 00: GUI (padrão 'BR.GOV.BCB.PIX')
    # subtag 01: chave
    mai = ""
    mai += _tag("00", "BR.GOV.BCB.PIX")
    if key:
        mai += _tag("01", key)
    # opcional: descrição (subtag 02) — deixamos vazio por padrão
    payload += _tag("26", mai)

    # 52 Merchant Category Code (0000 = unspecified)
    payload += _tag("52", "0000")

    # 53 Transaction Currency (986 = BRL)
    payload += _tag("53", "986")

    # 54 Transaction Amount (opcional)
    if amount is not None and str(amount).strip() != "":
        # garante formato com ponto decimal e duas casas
        try:
            amt = float(amount)
            amt_str = ("{:.2f}".format(amt)).replace(",", ".")
            payload += _tag("54", amt_str)
        except Exception:
            # se não converte, ignora o campo
            pass

    # 58 Country Code
    payload += _tag("58", "BR")

    # 59 Merchant Name (até 25)
    mn = (merchant_name or "")[:25]
    if not mn:
        mn = "ECOMMERCE"
    payload += _tag("59", mn)

    # 60 Merchant City (até 15)
    mc = (merchant_city or "")[:15]
    if not mc:
        mc = "BR"
    payload += _tag("60", mc)

    # 62 Additional Data Field Template — subtag 05 = TXID
    sub62 = _tag("05", txid or "")
    payload += _tag("62", sub62)

    # 63 CRC (placeholder '6304' + CRC-16)
    payload_for_crc = payload + "63" + "04"
    crc = _crc16_ccitt(payload_for_crc.encode("utf-8"))
    payload = payload + _tag("63", crc)

    return payload

@app.route("/finalizar_compra", methods=["GET", "POST"])
def finalizar_compra():
    if "usuario_id" not in session:
        flash("Faça login para finalizar a compra.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    # ==========================================================
    # FUNÇÃO STUB PSP (mantém sua lógica para cartão)
    # ==========================================================
    def process_payment_with_psp(payload):
        if payload.get("pagamento") == "cartao":
            if payload.get("psp_token"):
                return {
                    "ok": True,
                    "psp_token": payload.get("psp_token"),
                    "tipo": "cartao",
                    "bandeira": payload.get("bandeira"),
                    "ultimos4": payload.get("ultimos4"),
                    "nome_titular": payload.get("nome_titular"),
                    "expiracao": payload.get("expiracao")
                }

            card = payload.get("card_number", "") or ""
            ult4 = card[-4:] if len(card) >= 4 else None

            return {
                "ok": True,
                "psp_token": "tok_demo_" + (ult4 or "0000"),
                "tipo": "cartao",
                "bandeira": payload.get("bandeira") or "unknown",
                "ultimos4": ult4,
                "nome_titular": payload.get("nome_cartao") or payload.get("nome"),
                "expiracao": payload.get("expiracao")
            }

        return {"ok": True, "tipo": payload.get("pagamento")}

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ==========================================================
        # BUSCA ITENS DO CARRINHO
        # ==========================================================
        cursor.execute("""
            SELECT c.quantidade, p.id AS produto_id, p.nome, p.preco, p.estoque
            FROM carrinho c
            JOIN produtos p ON p.id = c.produto_id
            WHERE c.usuario_id = %s
        """, (usuario_id,))
        itens = cursor.fetchall()

        if not itens:
            cursor.close()
            conn.close()
            flash("Seu carrinho está vazio!", "erro")
            return redirect(url_for("loja"))

        # ==========================================================
        # GET: ABRE TELA DE FINALIZAÇÃO
        # ==========================================================
        if request.method == "GET":
            total = sum(item["quantidade"] * item["preco"] for item in itens)

            cursor.execute("""
                SELECT id, tipo, bandeira, ultimos4, nome_titular, expiracao, eh_padrao
                FROM metodo_pagamento
                WHERE cliente_id = %s
                ORDER BY eh_padrao DESC, criado_em DESC
            """, (usuario_id,))
            metodos_salvos = cursor.fetchall()

            cursor.close()
            conn.close()

            return render_template("finalizar.html",
                                   itens=itens,
                                   total=total,
                                   metodos_salvos=metodos_salvos)

        # ==========================================================
        # POST: PROCESSA FINALIZAÇÃO
        # ==========================================================
        required_fields = ["nome", "telefone", "endereco", "cep", "pagamento"]
        for field in required_fields:
            if not request.form.get(field):
                cursor.close()
                conn.close()
                flash("Todos os campos são obrigatórios!", "erro")
                return redirect(url_for("finalizar_compra"))

        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        endereco = request.form.get("endereco")
        cep = request.form.get("cep")
        pagamento = request.form.get("pagamento").strip().lower()

        save_card_flag = request.form.get("save_card") in ("1", "on")
        save_card_padrao = request.form.get("save_card_padrao") in ("1", "on")

        total = sum(item["quantidade"] * item["preco"] for item in itens)
        saved_method_id = request.form.get("saved_method_id")

        # ==========================================================
        # 🔵 FLUXO ESPECIAL PARA PIX
        # ==========================================================
        if pagamento == "pix":
            curw = conn.cursor()

            try:
                # cria pedido pendente
                curw.execute("""
                    INSERT INTO pedidos (cliente_id, total, data_, status)
                    VALUES (%s, %s, NOW(), %s)
                """, (usuario_id, total, "pendente"))
                pedido_id = curw.lastrowid

                # salva itens
                for item in itens:
                    curw.execute("""
                        INSERT INTO pedido_itens (pedido_id, produto_id, quantidade, preco_unitario)
                        VALUES (%s, %s, %s, %s)
                    """, (pedido_id, item["produto_id"], item["quantidade"], item["preco"]))

                    curw.execute("""
                        UPDATE produtos SET estoque = estoque - %s WHERE id = %s
                    """, (item["quantidade"], item["produto_id"]))

                # limpa carrinho
                curw.execute("DELETE FROM carrinho WHERE usuario_id = %s", (usuario_id,))

                conn.commit()

            except Exception as e:
                conn.rollback()
                print("Erro pedido PIX:", e)
                curw.close()
                cursor.close()
                conn.close()
                flash("Erro ao criar pedido PIX.", "erro")
                return redirect(url_for("finalizar_compra"))
            finally:
                curw.close()

            # ======================================================
            # GERAR PIX (USANDO SEU CPF COMO CHAVE)
            # ======================================================
            raw_pix_key = "141.284.919.50"
            PIX_KEY = "".join(ch for ch in raw_pix_key if ch.isdigit())  # → 14128491950

            txid = f"pedido-{pedido_id}"
            merchant_name = nome[:25] if nome else "CLIENTE"

            payload = build_pix_payload(
                key=PIX_KEY,
                txid=txid,
                amount=f"{total:.2f}",
                merchant_name=merchant_name,
                merchant_city="BR"
            )

            # gerar QRCode base64
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(payload)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            qr_b64 = base64.b64encode(buf.read()).decode("ascii")

            cursor.close()
            conn.close()

            session["checkout_info"] = {
                "pedido_id": pedido_id,
                "total": float(total),
                "pagamento": "pix"
            }

            return render_template("pagamentos_pix_checkout.html",
                                   pedido_id=pedido_id,
                                   total=total,
                                   payload=payload,
                                   qr_b64=qr_b64,
                                   merchant_name=merchant_name)

        # ==========================================================
        # 🔶 FLUXO PADRÃO (CARTÃO)
        # ==========================================================
        psp_res = None

        if pagamento == "cartao" and saved_method_id:
            cursor.execute("""
                SELECT id, token, tipo, bandeira, ultimos4, nome_titular, expiracao
                FROM metodo_pagamento
                WHERE id=%s AND cliente_id=%s
            """, (saved_method_id, usuario_id))
            mp = cursor.fetchone()

            if not mp:
                cursor.close()
                conn.close()
                flash("Método de pagamento inválido.", "erro")
                return redirect(url_for("finalizar_compra"))

            psp_res = {
                "ok": True,
                "psp_token": mp["token"],
                "tipo": "cartao",
                "bandeira": mp["bandeira"],
                "ultimos4": mp["ultimos4"],
                "nome_titular": mp["nome_titular"],
                "expiracao": mp["expiracao"]
            }

        else:
            payment_payload = {
                "pagamento": pagamento,
                "psp_token": request.form.get("psp_token"),
                "card_number": request.form.get("card_number"),
                "expiracao": request.form.get("expiracao"),
                "nome_cartao": request.form.get("nome_cartao"),
                "bandeira": request.form.get("bandeira"),
                "ultimos4": request.form.get("ultimos4"),
                "nome": nome
            }
            psp_res = process_payment_with_psp(payment_payload)

        if not psp_res["ok"]:
            cursor.close()
            conn.close()
            flash("Erro ao processar pagamento.", "erro")
            return redirect(url_for("finalizar_compra"))

        # ==========================================================
        # SALVAR PEDIDO NORMAL (CARTÃO)
        # ==========================================================
        cursor_w = conn.cursor()
        try:
            cursor_w.execute("""
                INSERT INTO pedidos (cliente_id, total, data_)
                VALUES (%s, %s, NOW())
            """, (usuario_id, total))
            pedido_id = cursor_w.lastrowid

            for item in itens:
                cursor_w.execute("""
                    INSERT INTO pedido_itens (pedido_id, produto_id, quantidade, preco_unitario)
                    VALUES (%s, %s, %s, %s)
                """, (pedido_id, item["produto_id"], item["quantidade"], item["preco"]))

                cursor_w.execute("UPDATE produtos SET estoque = estoque - %s WHERE id = %s",
                                 (item["quantidade"], item["produto_id"]))

            cursor_w.execute("DELETE FROM carrinho WHERE usuario_id = %s", (usuario_id,))

            conn.commit()

        finally:
            cursor_w.close()

        cursor.close()
        conn.close()

        return redirect(url_for("compra_sucesso", pedido_id=pedido_id))

    finally:
        try: cursor.close()
        except: pass
        try: conn.close()
        except: pass


@app.route("/pagamentos/novo", methods=["GET", "POST"])
def pagamentos_novo():
    if "usuario_id" not in session:
        flash("Faça login para gerenciar pagamentos.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    # GET: renderiza formulário
    if request.method == "GET":
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT nome, email, foto_usuario, horas_online FROM cliente WHERE id=%s", (usuario_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        foto = user.get("foto_usuario") if user else None
        foto_url = url_for("static", filename=foto.replace("static/", "")) if foto else url_for("static", filename="img/padrao_foto.png")

        return render_template("settings/pagamentos_novo.html",
                               usuario=(user["nome"] if user else None),
                               email=(user["email"] if user else None),
                               fotoUsuario=foto_url,
                               horas_online=(user.get("horas_online", 0) if user else 0))

    # POST: processa submissão e SALVA o método de pagamento (cartão)
    # Obs: este endpoint força a gravação para cartões (modo dev). Em produção, use token do PSP.
    pagamento = (request.form.get("pagamento") or "cartao").strip().lower()
    nome = (request.form.get("nome") or "").strip()
    # permite ao usuário indicar padrão
    save_card_padrao = request.form.get("save_card_padrao") in ("1", "on", "true", "True")

    # campos esperados do form / tokenização simulada
    psp_token = (request.form.get("psp_token") or "").strip() or None
    ultimos4 = (request.form.get("ultimos4") or "").strip() or None
    bandeira = (request.form.get("bandeira_hidden") or request.form.get("bandeira") or "").strip() or None
    expiracao = (request.form.get("expiracao") or "").strip() or None

    try:
        if pagamento != "cartao":
            flash("Tipo de pagamento inválido para salvar.", "erro")
            return redirect(url_for("pagamentos"))

        # validações mínimas (nome e ultimos4)
        if not nome:
            flash("Nome do titular é obrigatório.", "erro")
            return redirect(url_for("pagamentos_novo"))
        if not ultimos4 or len(ultimos4) < 3:
            # mesmo que não tenha ultimos4, permitimos salvar mas avisamos; aqui exigimos ter algo válido
            flash("Número do cartão inválido (últimos 4 dígitos).", "erro")
            return redirect(url_for("pagamentos_novo"))

        # se token não veio, geramos token demo (somente dev)
        if not psp_token:
            psp_token = "tok_demo_" + (ultimos4 or "0000")

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # se o novo método vem marcado como padrão, limpar anteriores
            if save_card_padrao:
                cur.execute("UPDATE metodo_pagamento SET eh_padrao=0 WHERE cliente_id=%s", (usuario_id,))

            cur.execute("""
                INSERT INTO metodo_pagamento
                  (cliente_id, tipo, bandeira, ultimos4, nome_titular, expiracao, token, eh_padrao, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                usuario_id,
                "cartao",
                bandeira,
                ultimos4,
                nome,
                expiracao,
                psp_token,
                1 if save_card_padrao else 0
            ))
            conn.commit()
            inserted_id = cur.lastrowid if hasattr(cur, "lastrowid") else None

            cur.close()
            conn.close()

            flash("Método salvo com sucesso.", "sucesso")
            return redirect(url_for("pagamentos"))

        except Exception as e_insert:
            # rollback e log
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                cur.close()
                conn.close()
            except Exception:
                pass
            print("Erro ao inserir metodo_pagamento:", repr(e_insert))
            flash("Erro ao salvar método de pagamento (veja logs).", "erro")
            return redirect(url_for("pagamentos"))

    except Exception as e:
        print("Erro processando novo método (outer):", repr(e))
        flash("Erro ao processar método de pagamento.", "erro")
        return redirect(url_for("pagamentos"))

@app.route("/compra_sucesso/<int:pedido_id>")
def compra_sucesso(pedido_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # pega dados do pedido (raw do DB)
    cursor.execute("""
        SELECT p.*, c.nome AS cliente_nome
        FROM pedidos p
        LEFT JOIN cliente c ON c.id = p.cliente_id
        WHERE p.id = %s
    """, (pedido_id,))
    pedido_db = cursor.fetchone()

    # itens do pedido
    cursor.execute("""
        SELECT i.quantidade, i.preco_unitario, pr.nome
        FROM pedido_itens i
        INNER JOIN produtos pr ON pr.id = i.produto_id
        WHERE i.pedido_id = %s
    """, (pedido_id,))
    itens = cursor.fetchall()

    # pega checkout_info salva na sessão (fluxo do finalizar_compra grava isso)
    checkout_info = session.pop("checkout_info", None)

    # monta um objeto compatível com o template (preenche telefone/endereco via checkout_info se faltar)
    pedido_for_template = {
        "id": pedido_id,
        "total": None,
        "nome": "",
        "telefone": "",
        "endereco": "",
        "cep": "",
        "pagamento": "",
        "data_": None
    }

    if pedido_db:
        pedido_for_template["total"] = pedido_db.get("total") or pedido_for_template["total"]
        pedido_for_template["nome"] = pedido_db.get("cliente_nome") or pedido_for_template["nome"]
        pedido_for_template["data_"] = pedido_db.get("data_") or pedido_for_template["data_"]
        # se a sua tabela pedidos tiver esses campos no futuro, usaremos:
        pedido_for_template["telefone"] = pedido_db.get("telefone") or pedido_for_template["telefone"]
        pedido_for_template["endereco"] = pedido_db.get("endereco") or pedido_for_template["endereco"]
        pedido_for_template["cep"] = pedido_db.get("cep") or pedido_for_template["cep"]
        pedido_for_template["pagamento"] = pedido_db.get("pagamento") or pedido_for_template["pagamento"]

    # fallback: completar com checkout_info (normalmente preenchido no fluxo do checkout)
    if checkout_info:
        pedido_for_template["total"] = pedido_for_template["total"] or checkout_info.get("total")
        pedido_for_template["nome"] = pedido_for_template["nome"] or checkout_info.get("nome")
        pedido_for_template["telefone"] = pedido_for_template["telefone"] or checkout_info.get("telefone")
        pedido_for_template["endereco"] = pedido_for_template["endereco"] or checkout_info.get("endereco")
        pedido_for_template["cep"] = pedido_for_template["cep"] or checkout_info.get("cep")
        pedido_for_template["pagamento"] = pedido_for_template["pagamento"] or checkout_info.get("pagamento")

    cursor.close()
    conn.close()

    return render_template(
        "sucesso.html",
        pedido=pedido_for_template,
        pedido_db=pedido_db,
        pedido_id=pedido_id,
        itens=itens,
        checkout=pedido_for_template,
        total=pedido_for_template.get("total")
    )

@app.route("/pagamentos/pix_confirmar", methods=["POST"])
def confirmar_pagamento_pix():
    if "usuario_id" not in session:
        flash("Faça login para confirmar pagamento.", "erro")
        return redirect(url_for("auth"))
    usuario_id = session["usuario_id"]
    pedido_id = request.form.get("pedido_id")
    if not pedido_id:
        flash("Pedido inválido.", "erro")
        return redirect(url_for("site"))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # opcional: verificar que o pedido pertence ao usuário
        cur.execute("SELECT cliente_id FROM pedidos WHERE id=%s", (pedido_id,))
        row = cur.fetchone()
        if not row:
            flash("Pedido não encontrado.", "erro")
            return redirect(url_for("site"))
        if int(row[0]) != int(usuario_id):
            flash("Não autorizado para confirmar este pedido.", "erro")
            return redirect(url_for("site"))

        cur.execute("UPDATE pedidos SET status=%s WHERE id=%s", ("processando", pedido_id))
        conn.commit()
        try:
            gravar_historico(cliente_id=usuario_id, admin_id=None, acao="pix_pago_manual", detalhes=f"Cliente marcou pedido #{pedido_id} como pago (manual).", ip=request.remote_addr, meta={"pedido_id": pedido_id})
        except Exception:
            pass

        flash("Pedido marcado como pago. Acompanhe o status em seus pedidos.", "sucesso")
        return redirect(url_for("compra_sucesso", pedido_id=pedido_id))
    except Exception as e:
        print("Erro confirmar pagamento PIX:", e)
        try: conn.rollback()
        except: pass
        flash("Erro ao confirmar pagamento.", "erro")
        return redirect(url_for("site"))
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass


@app.route("/suporte")
def suporte():
    # ================== BUSCA DADOS DO USUÁRIO ==================
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    if "usuario_id" in session:
        usuario_id = session["usuario_id"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT nome, email, foto_usuario, horas_online
            FROM cliente
            WHERE id = %s
        """, (usuario_id,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            usuario = user["nome"]
            email = user["email"]

            if user["foto_usuario"]:
                fotoUsuario = url_for(
                    "static",
                    filename=user["foto_usuario"].replace("static/", "")
                )

            horas_online = user.get("horas_online", 0)

    return render_template(
        "suporte.html",
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online
    )

@app.route("/admin")
def admin_index():
    print("DEBUG /admin:", session.get("admin_id"))
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    return render_template("admin/admin_index.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE email=%s AND senha=%s", (email, senha))
        admin = cursor.fetchone()
        cursor.close()
        db.close()

        if admin:
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_nome"] = admin["nome"]
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("admin_estatisticas"))
        else:
            flash("Credenciais incorretas!", "danger")

    return render_template("admin/admin_login.html")

@app.route("/admin/produtos")
def admin_produtos():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id ASC")
    produtos = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("admin/admin_produtos.html", produtos=produtos)

@app.route("/admin/produtos/novo", methods=["GET", "POST"])
def admin_produto_novo():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        nome = request.form.get("nome")
        descricao = request.form.get("descricao")
        preco = float(request.form.get("preco", 0))
        estoque = int(request.form.get("estoque", 0))
        imagem = request.files.get("imagem")

        # Salvar imagem
        filename = "default.png"
        if imagem:
            filename = secure_filename(imagem.filename)
            imagem.save(os.path.join("static/produtos", filename))

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO produtos (nome, descricao, preco, estoque, imagem)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, descricao, preco, estoque, filename))
        db.commit()
        cursor.close()
        db.close()

        flash("Produto adicionado com sucesso!", "sucesso")
        return redirect(url_for("admin_produtos"))

    return render_template("admin/admin_produto_novo.html")

@app.route("/admin/produtos/editar/<int:produto_id>", methods=["GET", "POST"])
def admin_produto_editar(produto_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos WHERE id=%s", (produto_id,))
    produto = cursor.fetchone()

    if not produto:
        flash("Produto não encontrado!", "erro")
        return redirect(url_for("admin_produtos"))

    if request.method == "POST":
        nome = request.form.get("nome")
        descricao = request.form.get("descricao")
        preco = float(request.form.get("preco", 0))
        estoque = int(request.form.get("estoque", 0))
        imagem = request.files.get("imagem")

        # Atualizar imagem se houver
        if imagem:
            filename = secure_filename(imagem.filename)
            imagem.save(os.path.join("static/produtos", filename))
        else:
            filename = produto["imagem"]

        cursor.execute("""
            UPDATE produtos
            SET nome=%s, descricao=%s, preco=%s, estoque=%s, imagem=%s
            WHERE id=%s
        """, (nome, descricao, preco, estoque, filename, produto_id))
        db.commit()
        cursor.close()
        db.close()

        flash("Produto atualizado com sucesso!", "sucesso")
        return redirect(url_for("admin_produtos"))

    cursor.close()
    db.close()
    return render_template("admin/admin_produto_editar.html", produto=produto)

@app.route("/admin/produtos/deletar/<int:produto_id>", methods=["POST"])
def admin_produto_deletar(produto_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM produtos WHERE id=%s", (produto_id,))
    db.commit()
    cursor.close()
    db.close()

    flash("Produto deletado com sucesso!", "info")
    return redirect(url_for("admin_produtos"))


#adm produtos CRUD

@app.route("/admin/pedidos")
def admin_pedidos():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.id, p.total, p.status, p.data_, c.nome AS cliente
        FROM pedidos p
        LEFT JOIN cliente c ON c.id = p.cliente_id
        ORDER BY p.data_ DESC
    """)
    pedidos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/admin_pedidos.html", pedidos=pedidos)


@app.route("/admin/pedidos/<int:pedido_id>")
def admin_pedido_detalhes(pedido_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, c.nome AS cliente_nome, c.email AS cliente_email
        FROM pedidos p
        JOIN cliente c ON c.id = p.cliente_id
        WHERE p.id = %s
    """, (pedido_id,))
    pedido = cursor.fetchone()

    if not pedido:
        flash("Pedido não encontrado!", "erro")
        return redirect(url_for("admin_pedidos"))

    cursor.execute("""
        SELECT pi.*, pr.nome AS produto_nome, pr.imagem
        FROM pedido_itens pi
        JOIN produtos pr ON pr.id = pi.produto_id
        WHERE pi.pedido_id = %s
    """, (pedido_id,))
    itens = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/admin_pedidos_detalhes.html",
                           pedido=pedido, itens=itens)

@app.route("/admin/pedidos/status/<int:pedido_id>", methods=["POST"])
def admin_pedido_status(pedido_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    novo_status = request.form.get("status")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pedidos SET status = %s WHERE id = %s
    """, (novo_status, pedido_id))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Status atualizado com sucesso!", "sucesso")
    return redirect(url_for("admin_pedido_detalhes", pedido_id=pedido_id))

@app.route("/admin/pedidos/deletar/<int:pedido_id>", methods=["POST"])
def admin_pedido_deletar(pedido_id):
    # segurança básica
    if "admin_id" not in session:
        flash("Faça login como administrador.", "erro")
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # verifica existência
        cur.execute("SELECT id, cliente_id, status FROM pedidos WHERE id=%s", (pedido_id,))
        pedido = cur.fetchone()
        if not pedido:
            flash("Pedido não encontrado.", "erro")
            return redirect(url_for("admin_pedidos"))

        # pega itens do pedido
        cur.execute("SELECT produto_id, quantidade FROM pedido_itens WHERE pedido_id=%s", (pedido_id,))
        itens = cur.fetchall()

        # cursor de escrita separado
        writer = conn.cursor()
        try:
            # restaura estoque — opcional conforme sua regra de negócio
            for it in itens:
                # proteja para caso produto não exista (não quebra a transação)
                writer.execute("UPDATE produtos SET estoque = COALESCE(estoque,0) + %s WHERE id = %s", (it["quantidade"], it["produto_id"]))

            # deleta itens e pedido
            writer.execute("DELETE FROM pedido_itens WHERE pedido_id=%s", (pedido_id,))
            writer.execute("DELETE FROM pedidos WHERE id=%s", (pedido_id,))

            conn.commit()
        except Exception as e_inner:
            conn.rollback()
            print("ERRO ao deletar pedido (inner):", e_inner)
            flash("Erro ao deletar pedido. Veja logs.", "erro")
            return redirect(url_for("admin_pedidos"))
        finally:
            try: writer.close()
            except: pass

        # grava histórico (se existir função)
        try:
            gravar_historico(cliente_id=pedido.get("cliente_id"), admin_id=session.get("admin_id"),
                             acao="pedido_deletado", detalhes=f"Pedido #{pedido_id} excluído pelo admin {session.get('admin_id')}",
                             ip=request.remote_addr, meta={"pedido_id": pedido_id})
        except Exception as e_hist:
            print("Aviso: falha ao gravar histórico:", e_hist)

        flash(f"Pedido #{pedido_id} excluído com sucesso.", "sucesso")
        return redirect(url_for("admin_pedidos"))

    except Exception as e:
        conn.rollback()
        print("ERRO ao deletar pedido (outer):", e)
        flash("Erro interno ao excluir pedido.", "erro")
        return redirect(url_for("admin_pedidos"))

    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

# =========================================================
#   ADMIN — CLIENTES (CRUD COMPLETO)
# =========================================================

def gravar_historico(cliente_id, admin_id, acao, detalhes=None, ip=None, meta=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cliente_historico (cliente_id, admin_id, acao, detalhes, ip_origem, meta)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        cliente_id,
        admin_id,
        acao,
        detalhes,
        ip,
        json.dumps(meta, ensure_ascii=False) if meta is not None else None
    ))
    conn.commit()
    cursor.close()
    conn.close()


@app.route("/admin/clientes")
def admin_clientes():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cliente ORDER BY id DESC")
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin/admin_clientes.html", clientes=clientes)


# -------- DETALHES DO CLIENTE -------------------------------------

@app.route("/admin/clientes/<int:cliente_id>")
def admin_cliente_detalhes(cliente_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Dados do cliente
    cursor.execute("SELECT * FROM cliente WHERE id=%s", (cliente_id,))
    cliente = cursor.fetchone()
    if not cliente:
        cursor.close()
        conn.close()
        flash("Cliente não encontrado!", "danger")
        return redirect(url_for("admin_clientes"))

    # Estatísticas do cliente (total de pedidos, soma dos totais)
    cursor.execute("""
        SELECT
            COUNT(*) AS total_pedidos,
            COALESCE(SUM(total), 0) AS total_gasto
        FROM pedidos
        WHERE cliente_id = %s
    """, (cliente_id,))
    stats = cursor.fetchone() or {"total_pedidos": 0, "total_gasto": 0.0}

    # Último pedido (mais recente)
    cursor.execute("""
        SELECT id, total, status, data_
        FROM pedidos
        WHERE cliente_id = %s
        ORDER BY data_ DESC
        LIMIT 1
    """, (cliente_id,))
    ultimo_pedido = cursor.fetchone()  # pode ser None

    # (Opcional) últimos 5 pedidos para seção inferior se quiser
    cursor.execute("""
        SELECT id, total, status, data_
        FROM pedidos
        WHERE cliente_id = %s
        ORDER BY data_ DESC
        LIMIT 5
    """, (cliente_id,))
    ultimos_pedidos = cursor.fetchall()

    cursor.close()
    conn.close()

    # Normalizar tipos (garantir números)
    stats["total_pedidos"] = int(stats.get("total_pedidos") or 0)
    try:
        stats["total_gasto"] = float(stats.get("total_gasto") or 0.0)
    except Exception:
        stats["total_gasto"] = 0.0

    return render_template(
        "admin/admin_cliente_detalhes.html",
        cliente=cliente,
        stats=stats,
        ultimo_pedido=ultimo_pedido,
        ultimos_pedidos=ultimos_pedidos
    )





# -------- EDITAR CLIENTE -------------------------------------

@app.route("/admin/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
def admin_cliente_editar(cliente_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM cliente WHERE id=%s", (cliente_id,))
    cliente = cursor.fetchone()

    if not cliente:
        flash("Cliente não encontrado!", "danger")
        return redirect(url_for("admin_clientes"))

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        status = request.form.get("status", "ativo")

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE cliente SET nome=%s, email=%s, status=%s
            WHERE id=%s
        """, (nome, email, status, cliente_id))

        conn.commit()
        cursor2.close()
        cursor.close()
        conn.close()

        flash("Cliente atualizado!", "success")
        return redirect(url_for("admin_cliente_detalhes", cliente_id=cliente_id))

    cursor.close()
    conn.close()
    return render_template("admin/admin_cliente_editar.html", cliente=cliente)




# -------- DELETAR CLIENTE -------------------------------------

@app.route("/admin/clientes/<int:cliente_id>/deletar", methods=["POST"])
def admin_cliente_deletar(cliente_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cliente WHERE id=%s", (cliente_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Cliente deletado!", "info")
    return redirect(url_for("admin_clientes"))


@app.route("/admin/clientes/<int:cliente_id>/historico")
def admin_cliente_historico(cliente_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Pedidos do cliente (mantemos)
    cursor.execute("""
        SELECT id, total, status, data_
        FROM pedidos
        WHERE cliente_id=%s
        ORDER BY data_ DESC
        LIMIT 20
    """, (cliente_id,))
    pedidos = cursor.fetchall()

    # Para cada pedido, pegar 1 item (nome + imagem) — melhora visual do histórico
    for p in pedidos:
        try:
            cursor.execute("""
                SELECT pr.nome AS produto_nome, pr.imagem AS produto_imagem
                FROM pedido_itens pi
                JOIN produtos pr ON pr.id = pi.produto_id
                WHERE pi.pedido_id = %s
                LIMIT 1
            """, (p["id"],))
            first_item = cursor.fetchone()
            if first_item:
                p["produto_nome"] = first_item.get("produto_nome")
                p["produto_imagem"] = first_item.get("produto_imagem")
            else:
                p["produto_nome"] = None
                p["produto_imagem"] = None
        except Exception:
            p["produto_nome"] = None
            p["produto_imagem"] = None

    # Histórico de ações (tabela cliente_historico)
    cursor.execute("""
        SELECT id, admin_id, acao, detalhes, ip_origem, meta, criado_em
        FROM cliente_historico
        WHERE cliente_id=%s
        ORDER BY criado_em DESC
        LIMIT 200
    """, (cliente_id,))
    historico = cursor.fetchall()

    # Dados básicos do cliente
    cursor.execute("SELECT id, nome, email, foto_usuario FROM cliente WHERE id=%s", (cliente_id,))
    cliente = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/admin_cliente_historico.html",
                           cliente=cliente,
                           pedidos=pedidos,
                           historico=historico)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Admin saiu da conta.", "info")
    return redirect(url_for("admin_login"))

@app.route("/admin/estatisticas")
def admin_estatisticas():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Total de vendas
    cursor.execute("SELECT SUM(total) AS total_vendas FROM pedidos")
    total_vendas = cursor.fetchone()["total_vendas"] or 0

    # Total de pedidos
    cursor.execute("SELECT COUNT(*) AS total_pedidos FROM pedidos")
    total_pedidos = cursor.fetchone()["total_pedidos"]

    # Últimos 5 pedidos
    cursor.execute("""
        SELECT pedidos.id, cliente.nome, pedidos.total, pedidos.data_
        FROM pedidos
        JOIN cliente ON cliente.id = pedidos.cliente_id
        ORDER BY pedidos.data_ DESC
        LIMIT 5
    """)
    ultimos_pedidos = cursor.fetchall()

    # Feedbacks recentes
    cursor.execute("""
        SELECT mensagem, data_envio
        FROM feedbacks
        ORDER BY data_envio DESC
        LIMIT 5
    """)
    feedbacks = cursor.fetchall()

    # Top 5 produtos mais vendidos
    cursor.execute("""
        SELECT produtos.nome, SUM(pedido_itens.quantidade) AS quantidade
        FROM pedido_itens
        JOIN produtos ON produtos.id = pedido_itens.produto_id
        GROUP BY produtos.id
        ORDER BY quantidade DESC
        LIMIT 5
    """)
    mais_vendidos = cursor.fetchall()

    # Estoque baixo
    cursor.execute("""
        SELECT nome, estoque
        FROM produtos
        WHERE estoque < 5
    """)
    estoque_baixo = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin/estatisticas.html",
        total_vendas=total_vendas,
        total_pedidos=total_pedidos,
        ultimos_pedidos=ultimos_pedidos,
        feedbacks=feedbacks,
        mais_vendidos=mais_vendidos,
        estoque_baixo=estoque_baixo
    )


# =========================
# CONFIGURAÇÕES (Perfil etc)
# =========================
from werkzeug.security import generate_password_hash, check_password_hash  # opcional, ver observações

@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if "usuario_id" not in session:
        flash("Faça login para acessar o perfil.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        pais = request.form.get("pais_regiao", "br")

        if not nome or not email:
            flash("Nome e e-mail são obrigatórios.", "erro")
            return redirect(url_for("perfil") + '#perfil')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # email único
            cursor.execute("SELECT id FROM cliente WHERE email=%s AND id<>%s", (email, usuario_id))
            if cursor.fetchone():
                flash("Este e-mail já está em uso por outro usuário.", "erro")
                return redirect(url_for("perfil") + '#perfil')

            # pega foto atual
            cursor.execute("SELECT foto_usuario FROM cliente WHERE id=%s", (usuario_id,))
            row = cursor.fetchone()
            foto_atual = row["foto_usuario"] if row and row.get("foto_usuario") else None

            remover_flag = request.form.get("remover_foto", "0") == "1"
            foto_path = None

            # pega o objeto do arquivo (pode existir key mesmo sem arquivo selecionado)
            f = request.files.get("foto")

            # --- Caso 1: upload válido (tem arquivo escolhido) ---
            if f and getattr(f, "filename", ""):
                # validação da extensão
                allowed_ext = {".jpg", ".jpeg", ".png", ".webp"}
                _, ext = os.path.splitext(f.filename.lower())
                if ext not in allowed_ext:
                    flash("Tipo de imagem não permitido. Use jpg, png ou webp.", "erro")
                    return redirect(url_for("perfil") + '#perfil')

                # validação de tamanho (opcional)
                max_size_mb = 5
                f.seek(0, os.SEEK_END)
                tamanho = f.tell()
                f.seek(0)
                if tamanho > max_size_mb * 1024 * 1024:
                    flash(f"A imagem é muito grande. Máximo: {max_size_mb}MB.", "erro")
                    return redirect(url_for("perfil") + '#perfil')

                filename = secure_filename(f.filename)
                filename = f"user_{usuario_id}_{int(datetime.utcnow().timestamp())}{ext}"
                upload_dir = os.path.join("static", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                dest = os.path.join(upload_dir, filename)
                try:
                    f.save(dest)
                    foto_path = os.path.join("static", "uploads", filename).replace("\\", "/")
                except Exception as e:
                    print("Erro ao salvar imagem:", e)
                    flash("Erro ao salvar imagem. Tente novamente.", "erro")
                    return redirect(url_for("perfil") + '#perfil')

                # opcional: remover a antiga se for upload nosso
                try:
                    if foto_atual and foto_atual.startswith("static/uploads/") and not remover_flag:
                        old_fs = os.path.join(os.getcwd(), foto_atual)
                        if os.path.exists(old_fs) and os.path.isfile(old_fs):
                            os.remove(old_fs)
                except Exception as e:
                    print("Erro ao apagar foto antiga (opcional):", e)

            else:
                # --- Caso 2: não houve upload válido; se marcaram remoção, tratamos remoção ---
                if remover_flag:
                    # apagar fisicamente se for upload nosso
                    try:
                        if foto_atual and foto_atual.startswith("static/uploads/"):
                            old_fs = os.path.join(os.getcwd(), foto_atual)
                            if os.path.exists(old_fs) and os.path.isfile(old_fs):
                                os.remove(old_fs)
                    except Exception as e:
                        print("Erro ao apagar foto antiga durante remoção:", e)
                    # definimos foto padrão a ser salva no DB
                    foto_path = "static/img/padrao_foto.png"
                # --- Caso 3: sem upload e sem remoção -> manter foto_atual (não alterar foto_path) ---

            # --- Atualiza DB ---
            if foto_path is not None:
                cursor_up = conn.cursor()
                cursor_up.execute("""
                    UPDATE cliente
                    SET nome=%s, email=%s, pais_regiao=%s, foto_usuario=%s
                    WHERE id=%s
                """, (nome, email, pais, foto_path, usuario_id))
                cursor_up.close()
            else:
                cursor_up = conn.cursor()
                cursor_up.execute("""
                    UPDATE cliente
                    SET nome=%s, email=%s, pais_regiao=%s
                    WHERE id=%s
                """, (nome, email, pais, usuario_id))
                cursor_up.close()

            conn.commit()
            flash("Perfil atualizado com sucesso.", "sucesso")
            return redirect(url_for('perfil') + '#perfil')


        except Exception as e:
            print("Erro ao atualizar perfil:", e)
            conn.rollback()
            flash("Erro ao atualizar perfil. Tente novamente.", "erro")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("perfil") + '#perfil')

    # GET: carrega dados
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, email, foto_usuario, pais_regiao, horas_online, receber_promocoes, notificacoes_pedido, alertas_seguranca FROM cliente WHERE id=%s", (usuario_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("auth"))

    foto_val = user.get("foto_usuario") or "static/img/padrao_foto.png"
    return render_template(
        "settings/perfil.html",
        usuario=user["nome"],
        email=user["email"],
        fotoUsuario=(foto_val if foto_val.startswith("http") else url_for('static', filename=foto_val.replace('static/', ''))),
        horas_online=user.get("horas_online", 0),
        user=user
    )

def _processar_troca_senha(usuario_id, form):
    atual = form.get("senha_atual", "").strip()
    nova = form.get("nova_senha", "").strip()
    conf = form.get("confirmar_senha", "").strip()

    if not atual or not nova or not conf:
        return False, "Preencha todos os campos."

    if nova != conf:
        return False, "As senhas não coincidem."

    if len(nova) < 8:
        return False, "A nova senha deve ter pelo menos 8 caracteres."

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT senha FROM cliente WHERE id=%s", (usuario_id,))
    row = cur.fetchone()
    if not row:
        return False, "Usuário não encontrado."

    senha_db = row["senha"]

    # --- CORREÇÃO AQUI ---
    # Suporte para senhas antigas sem hash
    if senha_db == atual:
        senha_valida = True
    else:
        senha_valida = check_password_hash(senha_db, atual)

    if not senha_valida:
        return False, "Senha atual incorreta."

    # gera hash novo
    novo_hash = generate_password_hash(nova)

    cur.execute("UPDATE cliente SET senha=%s WHERE id=%s", (novo_hash, usuario_id))
    conn.commit()

    cur.close()
    conn.close()

    return True, "Senha alterada com sucesso."


# ROTA compatível: aceita POST vindo do seu form action="{{ url_for('atualizar_senha') }}"
@app.route("/seguranca/atualizar-senha", methods=['POST'])
def atualizar_senha():
    if 'usuario_id' not in session:
        flash("Faça login para alterar sua senha.", "erro")
        return redirect(url_for('auth'))

    usuario_id = session['usuario_id']
    ok, msg = _processar_troca_senha(usuario_id, request.form)
    flash(msg, "sucesso" if ok else "erro")
    # redireciona para a aba 'Segurança' da página de configurações/perfil
    return redirect(url_for('perfil') + '#seguranca')




# ROTA unificada GET+POST
@app.route("/seguranca", methods=["GET", "POST"])
def seguranca():
    if "usuario_id" not in session:
        flash("Faça login para acessar as configurações.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    if request.method == "POST":
        ok, msg = _processar_troca_senha(usuario_id, request.form)
        flash(msg, "sucesso" if ok else "erro")
        return redirect(url_for('perfil') + '#seguranca')



    # GET: renderizar a página
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT id, nome, email, foto_usuario, pais_regiao, horas_online,
                      receber_promocoes, notificacoes_pedido, alertas_seguranca
                      FROM cliente WHERE id=%s""", (usuario_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("auth"))

    foto_val = user.get("foto_usuario") or "static/img/padrao_foto.png"
    return render_template(
        "settings/seguranca.html",
        usuario=user["nome"],
        email=user["email"],
        fotoUsuario=(foto_val if foto_val.startswith("http") else url_for('static', filename=foto_val.replace('static/', ''))),
        horas_online=user.get("horas_online", 0),
        user=user
    )


@app.route("/perfil/notificacoes", methods=["GET"])
@app.route("/notificacoes", methods=["GET"])
def notificacoes():
    if "usuario_id" not in session:
        flash("Faça login para acessar as configurações.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, nome, email, foto_usuario, horas_online,
               receber_promocoes, notificacoes_pedido, alertas_seguranca
        FROM cliente
        WHERE id=%s
    """, (usuario_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("auth"))

    foto_val = user.get("foto_usuario") or "static/img/padrao_foto.png"

    return render_template(
        "settings/notificacoes.html",
        usuario=user["nome"],
        email=user["email"],
        fotoUsuario=(foto_val if foto_val.startswith("http")
                     else url_for('static', filename=foto_val.replace('static/', ''))),
        horas_online=user.get("horas_online", 0),
        user=user
    )




@app.route("/config/notificacoes", methods=["POST"])
def atualizar_notificacoes():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401

    usuario_id = session["usuario_id"]

    # recebe JSON do fetch()
    data = request.get_json(silent=True) or {}

    receber = 1 if data.get("receber_promocoes") else 0
    pedidos = 1 if data.get("notificacoes_pedido") else 0
    alertas = 1 if data.get("alertas_seguranca") else 0

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE cliente
            SET receber_promocoes=%s,
                notificacoes_pedido=%s,
                alertas_seguranca=%s
            WHERE id=%s
        """, (receber, pedidos, alertas, usuario_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "Preferências atualizadas"})
    
    except Exception as e:
        print("Erro ao salvar notificações:", e)
        return jsonify({"error": "Erro interno ao salvar."}), 500


from flask import jsonify

@app.route("/notificacoes/salvar", methods=["POST"])
def salvar_notificacoes():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "error": "Não autorizado"}), 401

    usuario_id = session["usuario_id"]
    data = request.get_json(silent=True) or {}

    receber = 1 if data.get("receber_promocoes") else 0
    pedidos = 1 if data.get("notificacoes_pedido") else 0
    alertas = 1 if data.get("alertas_seguranca") else 0

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE cliente
            SET receber_promocoes=%s,
                notificacoes_pedido=%s,
                alertas_seguranca=%s
            WHERE id=%s
        """, (receber, pedidos, alertas, usuario_id))

        conn.commit()

        # opcional: pegar os valores salvos para confirmar
        cur2 = conn.cursor(dictionary=True)
        cur2.execute("SELECT receber_promocoes, notificacoes_pedido, alertas_seguranca FROM cliente WHERE id=%s", (usuario_id,))
        saved = cur2.fetchone()
        cur2.close()

        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "Preferências salvas.", "saved": saved}), 200

    except Exception as e:
        print("Erro ao salvar notificações:", repr(e))
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "Erro interno ao salvar"}), 500
    
@app.route("/privacidade", methods=["GET"])
def privacidade():
    if "usuario_id" not in session:
        flash("Faça login para acessar as configurações.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nome, email, foto_usuario, pais_regiao, horas_online, receber_promocoes, notificacoes_pedido, alertas_seguranca FROM cliente WHERE id=%s", (usuario_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("auth"))

    foto_val = user.get("foto_usuario") or "static/img/padrao_foto.png"
    return render_template(
        "settings/privacidade.html",
        usuario=user["nome"],
        email=user["email"],
        fotoUsuario=(foto_val if foto_val.startswith("http") else url_for('static', filename=foto_val.replace('static/', ''))),
        horas_online=user.get("horas_online", 0),
        user=user
    )



@app.route("/configuracoes/privacidade/solicitar-copia", methods=["POST"])
def solicitar_copia_dados():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "error": "login_required"}), 401

    usuario_id = session["usuario_id"]

    try:
        gravar_historico(
            cliente_id=usuario_id,
            admin_id=None,
            acao="solicitou_copia_dados",
            detalhes=None,
            ip=request.remote_addr,
            meta=None
        )
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "message": "Pedido recebido. Você será notificado por e-mail quando o arquivo estiver pronto."
    }), 200



def salvar_metodo_pagamento_if_needed(usuario_id, payment_info, save_card):
    """
    Salva método de pagamento para o usuário se save_card for truthy.
    payment_info: dict esperado com chaves (tipo, bandeira, ultimos4, nome_titular, expiracao, token, eh_padrao)
    NOTA: nunca armazene PAN/CVV completos. Use token do PSP.
    """
    if not save_card:
        return False

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # se o novo método vier marcado como padrão, limpar antigos
        if payment_info.get('eh_padrao'):
            cur.execute("UPDATE metodo_pagamento SET eh_padrao=0 WHERE cliente_id=%s", (usuario_id,))

        cur.execute("""
            INSERT INTO metodo_pagamento
              (cliente_id, tipo, bandeira, ultimos4, nome_titular, expiracao, token, eh_padrao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            usuario_id,
            payment_info.get('tipo'),
            payment_info.get('bandeira'),
            payment_info.get('ultimos4'),
            payment_info.get('nome_titular'),
            payment_info.get('expiracao'),
            payment_info.get('token'),
            1 if payment_info.get('eh_padrao') else 0
        ))

        conn.commit()
        return True
    except Exception as e:
        # log simples — se quiser, substitua por logger
        print("Erro ao salvar método de pagamento:", e)
        if conn:
            try: conn.rollback()
            except: pass
        return False
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass


@app.route("/pagamentos", methods=["GET"])
def pagamentos():
    if "usuario_id" not in session:
        flash("Faça login para acessar as configurações.", "erro")
        return redirect(url_for("auth"))

    usuario_id = session["usuario_id"]

    # ================== DADOS DO USUÁRIO ==================
    usuario = None
    email = None
    fotoUsuario = url_for('static', filename='img/padrao_foto.png')
    horas_online = 0

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT nome, email, foto_usuario, horas_online
        FROM cliente
        WHERE id = %s
    """, (usuario_id,))
    user = cursor.fetchone()

    if user:
        usuario = user["nome"]
        email = user["email"]
        horas_online = user.get("horas_online", 0)

        if user["foto_usuario"]:
            fotoUsuario = url_for(
                "static",
                filename=user["foto_usuario"].replace("static/", "")
            )

    # ================== MÉTODOS DE PAGAMENTO ==================
    cursor.execute("""
        SELECT id, tipo, bandeira, ultimos4, nome_titular, expiracao, eh_padrao, criado_em
        FROM metodo_pagamento
        WHERE cliente_id = %s
        ORDER BY eh_padrao DESC, criado_em DESC
    """, (usuario_id,))
    methods = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "settings/pagamentos.html",
        usuario=usuario,
        email=email,
        fotoUsuario=fotoUsuario,
        horas_online=horas_online,
        user={'metodos': methods}
    )


@app.route("/pagamentos/remover", methods=["POST"])
def pagamentos_remover():
    if "usuario_id" not in session:
        return jsonify(ok=False, error="login_required"), 401
    usuario_id = session["usuario_id"]
    data = request.get_json() or {}
    mid = data.get("id")
    if not mid:
        return jsonify(ok=False, error="missing_id"), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_pagamento WHERE id=%s AND cliente_id=%s", (mid, usuario_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(ok=True)
    except Exception as e:
        print("Erro remover método:", e)
        return jsonify(ok=False, error="server_error"), 500

@app.route("/pagamentos/definir_padrao", methods=["POST"])
def pagamentos_definir_padrao():
    if "usuario_id" not in session:
        return jsonify(ok=False, error="login_required"), 401
    usuario_id = session["usuario_id"]
    data = request.get_json() or {}
    mid = data.get("id")
    if not mid:
        return jsonify(ok=False, error="missing_id"), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE metodo_pagamento SET eh_padrao=0 WHERE cliente_id=%s", (usuario_id,))
        cur.execute("UPDATE metodo_pagamento SET eh_padrao=1 WHERE id=%s AND cliente_id=%s", (mid, usuario_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(ok=True)
    except Exception as e:
        print("Erro definir padrao:", e)
        return jsonify(ok=False, error="server_error"), 500


if __name__ == "__main__":
    app.run(debug=True)
