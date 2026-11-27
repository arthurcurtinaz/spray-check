import streamlit as st
import cv2
import numpy as np
import math
import pandas as pd
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Spray Check — Diagnóstico de Pulverização",
    page_icon="🌱",
    layout="wide"
)

# --- CONFIGURAÇÃO DE PWA PARA INSTALAÇÃO DIRETA NO CELULAR ---
pwa_code = """
<link rel="manifest" href="data:application/manifest+json,{
  &quot;name&quot;: &quot;Spray Check&quot;,
  &quot;short_name&quot;: &quot;SprayCheck&quot;,
  &quot;start_url&quot;: &quot;.&quot;,
  &quot;display&quot;: &quot;standalone&quot;,
  &quot;background_color&quot;: &quot;#ffffff&quot;,
  &quot;theme_color&quot;: &quot;#1b5e20&quot;,
  &quot;icons&quot;: [
    {
      &quot;src&quot;: &quot;https://cdn-icons-png.flaticon.com/512/628/628283.png&quot;,
      &quot;sizes&quot;: &quot;512x512&quot;,
      &quot;type&quot;: &quot;image/png&quot;
    }
  ]
}">
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('data:text/javascript,self.addEventListener("fetch", function(e) {});');
  }
</script>
"""
st.markdown(pwa_code, unsafe_allow_html=True)

# ==============================================================================
# 📊 BANCO DE CRITÉRIOS AGRONÔMICOS (EDITE AQUI COM SEUS DADOS DE CAMPO!)
# ==============================================================================
# Estrutura:
# "Tipo de Aplicação": {
#     "Estrato": {
#         "gotas_bom": X,   -> Mínimo de gotas/cm² para ser ADEQUADO
#         "gotas_aten": Y,  -> Mínimo de gotas/cm² para ser ATENÇÃO (abaixo disso = RUIM)
#         "cob_bom": A,     -> Mínimo de cobertura (%) para ser ADEQUADO
#         "cob_aten": B     -> Mínimo de cobertura (%) para ser ATENÇÃO
#     }
# }
# ==============================================================================

CRITERIOS_AGRONOMICOS = {
    "Herbicida de Contato": {
        "Terço Superior": {"gotas_bom": 40, "gotas_aten": 25, "cob_bom": 4.0, "cob_aten": 2.0},
        "Terço Médio":    {"gotas_bom": 30, "gotas_aten": 20, "cob_bom": 3.0, "cob_aten": 1.5},
        "Terço Inferior": {"gotas_bom": 25, "gotas_aten": 15, "cob_bom": 2.0, "cob_aten": 1.0},
        "Face Abaxial":   {"gotas_bom": 20, "gotas_aten": 10, "cob_bom": 1.5, "cob_aten": 0.8},
    },
    "Herbicida Sistêmico": {
        "Terço Superior": {"gotas_bom": 25, "gotas_aten": 15, "cob_bom": 2.5, "cob_aten": 1.2},
        "Terço Médio":    {"gotas_bom": 20, "gotas_aten": 12, "cob_bom": 2.0, "cob_aten": 1.0},
        "Terço Inferior": {"gotas_bom": 15, "gotas_aten": 10, "cob_bom": 1.5, "cob_aten": 0.8},
        "Face Abaxial":   {"gotas_bom": 15, "gotas_aten": 8,  "cob_bom": 1.0, "cob_aten": 0.5},
    },
    "Fungicida": {
        "Terço Superior": {"gotas_bom": 70, "gotas_aten": 45, "cob_bom": 5.0, "cob_aten": 3.0},
        "Terço Médio":    {"gotas_bom": 55, "gotas_aten": 35, "cob_bom": 4.0, "cob_aten": 2.0},
        "Terço Inferior": {"gotas_bom": 40, "gotas_aten": 25, "cob_bom": 2.5, "cob_aten": 1.5},
        "Face Abaxial":   {"gotas_bom": 30, "gotas_aten": 15, "cob_bom": 2.0, "cob_aten": 1.0},
    },
    "Inseticida": {
        "Terço Superior": {"gotas_bom": 50, "gotas_aten": 30, "cob_bom": 4.0, "cob_aten": 2.0},
        "Terço Médio":    {"gotas_bom": 40, "gotas_aten": 25, "cob_bom": 3.0, "cob_aten": 1.5},
        "Terço Inferior": {"gotas_bom": 30, "gotas_aten": 18, "cob_bom": 2.0, "cob_aten": 1.0},
        "Face Abaxial":   {"gotas_bom": 25, "gotas_aten": 12, "cob_bom": 1.5, "cob_aten": 0.8},
    }
}

# ==============================================================================
# 🎨 FUNÇÃO DE ILUSTRAÇÃO DA PLANTA (SVG DINÂMICO)
# ==============================================================================
def desenhar_planta_svg(cultura):
    if cultura == "Soja":
        planta_elementos = """
        <!-- Caule -->
        <path d="M150,360 Q145,220 150,70" stroke="#2e7d32" stroke-width="6" fill="none" stroke-linecap="round"/>
        <!-- Folhas Terço Superior -->
        <ellipse cx="120" cy="95" rx="28" ry="14" transform="rotate(-25 120 95)" fill="#66bb6a"/>
        <ellipse cx="180" cy="90" rx="28" ry="14" transform="rotate(20 180 90)" fill="#66bb6a"/>
        <ellipse cx="150" cy="65" rx="16" ry="24" fill="#81c784"/>
        <!-- Folhas Terço Médio -->
        <ellipse cx="105" cy="185" rx="36" ry="18" transform="rotate(-15 105 185)" fill="#43a047"/>
        <ellipse cx="195" cy="180" rx="36" ry="18" transform="rotate(15 195 180)" fill="#43a047"/>
        <!-- Folhas Terço Inferior -->
        <ellipse cx="100" cy="280" rx="40" ry="20" transform="rotate(-10 100 280)" fill="#2e7d32"/>
        <ellipse cx="200" cy="275" rx="40" ry="20" transform="rotate(10 200 275)" fill="#2e7d32"/>
        """
    elif cultura == "Milho":
        planta_elementos = """
        <!-- Colmo -->
        <line x1="150" y1="360" x2="150" y2="65" stroke="#388e3c" stroke-width="8" stroke-linecap="round"/>
        <!-- Pendão -->
        <path d="M150,65 L135,40 M150,65 L150,35 M150,65 L165,40" stroke="#fbc02d" stroke-width="3"/>
        <!-- Folhas arqueadas Superior -->
        <path d="M150,105 Q100,80 75,115 Q115,105 150,115" fill="#66bb6a"/>
        <path d="M150,100 Q200,75 225,110 Q185,100 150,110" fill="#66bb6a"/>
        <!-- Folhas arqueadas Médio -->
        <path d="M150,190 Q85,160 55,205 Q105,190 150,200" fill="#43a047"/>
        <path d="M150,185 Q215,155 245,200 Q195,185 150,195" fill="#43a047"/>
        <!-- Folhas arqueadas Inferior -->
        <path d="M150,280 Q80,255 50,300 Q105,280 150,290" fill="#2e7d32"/>
        <path d="M150,275 Q220,250 250,295 Q195,275 150,285" fill="#2e7d32"/>
        """
    else:  # Trigo
        planta_elementos = """
        <!-- Colmo fino -->
        <line x1="150" y1="360" x2="150" y2="95" stroke="#558b2f" stroke-width="5"/>
        <!-- Espiga -->
        <rect x="142" y="40" width="16" height="55" rx="8" fill="#fdd835" stroke="#f9a825" stroke-width="2"/>
        <!-- Folhas estreitas -->
        <path d="M150,115 Q105,100 85,130" stroke="#7cb342" stroke-width="6" fill="none" stroke-linecap="round"/>
        <path d="M150,190 Q195,175 215,205" stroke="#558b2f" stroke-width="6" fill="none" stroke-linecap="round"/>
        <path d="M150,275 Q100,260 80,295" stroke="#33691e" stroke-width="6" fill="none" stroke-linecap="round"/>
        """

    svg_completo = f"""
    <div style="display: flex; justify-content: center; background-color: #f8faf8; border-radius: 14px; padding: 15px; border: 1px solid #dcedc8;">
    <svg width="430" height="390" viewBox="0 0 430 390" xmlns="http://www.w3.org/2000/svg">
        <!-- Solo -->
        <ellipse cx="150" cy="365" rx="95" ry="12" fill="#8d6e63" opacity="0.5"/>
        {planta_elementos}
        
        <!-- Linhas indicativas e Rótulos dos Estratos -->
        <!-- 1. Terço Superior -->
        <line x1="185" y1="90" x2="275" y2="70" stroke="#1b5e20" stroke-width="2" stroke-dasharray="4"/>
        <circle cx="185" cy="90" r="5" fill="#1b5e20"/>
        <rect x="275" y="52" width="145" height="34" rx="6" fill="#e8f5e9" stroke="#2e7d32"/>
        <text x="347" y="74" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1b5e20" text-anchor="middle">1. Terço Superior</text>

        <!-- 2. Terço Médio -->
        <line x1="205" y1="180" x2="275" y2="160" stroke="#1b5e20" stroke-width="2" stroke-dasharray="4"/>
        <circle cx="205" cy="180" r="5" fill="#1b5e20"/>
        <rect x="275" y="142" width="145" height="34" rx="6" fill="#e8f5e9" stroke="#2e7d32"/>
        <text x="347" y="164" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1b5e20" text-anchor="middle">2. Terço Médio</text>

        <!-- 3. Terço Inferior -->
        <line x1="205" y1="275" x2="275" y2="250" stroke="#1b5e20" stroke-width="2" stroke-dasharray="4"/>
        <circle cx="205" cy="275" r="5" fill="#1b5e20"/>
        <rect x="275" y="232" width="145" height="34" rx="6" fill="#e8f5e9" stroke="#2e7d32"/>
        <text x="347" y="254" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1b5e20" text-anchor="middle">3. Terço Inferior</text>

        <!-- 4. Face Abaxial (Verso da folha) -->
        <line x1="115" y1="195" x2="275" y2="335" stroke="#0277bd" stroke-width="2" stroke-dasharray="4"/>
        <circle cx="115" cy="195" r="5" fill="#0277bd"/>
        <rect x="275" y="317" width="145" height="34" rx="6" fill="#e1f5fe" stroke="#0288d1"/>
        <text x="347" y="339" font-family="sans-serif" font-size="13" font-weight="bold" fill="#01579b" text-anchor="middle">4. Face Abaxial</text>
    </svg>
    </div>
    """
    return svg_completo


# ==============================================================================
# 💧 MOTOR DE VISÃO COMPUTACIONAL (CANAL VERDE FIXO + OTSU INDIVIDUAL)
# ==============================================================================
def analisar_cartao(uploaded_file, area_fisica_cm2, offset_otsu=0, usar_teto=True, diametro_teto_max=800.0):
    image_pil = Image.open(uploaded_file).convert('RGB')
    img_bgr = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

    altura_px, largura_px, _ = img_bgr.shape
    total_pixels_img = largura_px * altura_px

    # Canal Verde Fixo (índice 1 no BGR)
    img_verde = img_bgr[:, :, 1]

    # Limiar de Otsu calculado individualmente para cada foto
    limiar_otsu, _ = cv2.threshold(img_verde, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    limiar_final = int(max(0, min(255, limiar_otsu + offset_otsu)))
    _, img_binaria = cv2.threshold(img_verde, limiar_final, 255, cv2.THRESH_BINARY_INV)

    area_total_um2 = area_fisica_cm2 * 100000000.0
    area_por_pixel_um2 = area_total_um2 / total_pixels_img if total_pixels_img > 0 else 1.0

    contornos, _ = cv2.findContours(img_binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    total_gotas = 0
    soma_area_gotas_px = 0
    diametros_lista = []
    volumes_lista = []

    for c in contornos:
        area_px = cv2.contourArea(c)
        if area_px > 0:
            area_um2 = area_px * area_por_pixel_um2
            diametro_um = 2 * math.sqrt(area_um2 / math.pi)

            if usar_teto and diametro_um > diametro_teto_max:
                continue

            soma_area_gotas_px += area_px
            total_gotas += 1
            volume_gota = (math.pi / 6.0) * (diametro_um ** 3)
            diametros_lista.append(diametro_um)
            volumes_lista.append(volume_gota)

    densidade_gotas_cm2 = total_gotas / area_fisica_cm2 if area_fisica_cm2 > 0 else 0.0
    cobertura_pct = (soma_area_gotas_px / total_pixels_img * 100.0) if total_pixels_img > 0 else 0.0

    dmv, span, pct_deriva, pct_escorrimento = 0.0, 0.0, 0.0, 0.0
    if total_gotas > 0:
        dados_ord = sorted(zip(diametros_lista, volumes_lista), key=lambda x: x[0])
        d_arr = np.array([x[0] for x in dados_ord])
        v_arr = np.array([x[1] for x in dados_ord])

        vol_acum = np.cumsum(v_arr)
        vol_total = vol_acum[-1]

        if vol_total > 0:
            vol_rel = vol_acum / vol_total
            d01 = d_arr[min(np.searchsorted(vol_rel, 0.10), len(d_arr) - 1)]
            dmv = d_arr[min(np.searchsorted(vol_rel, 0.50), len(d_arr) - 1)]
            d09 = d_arr[min(np.searchsorted(vol_rel, 0.90), len(d_arr) - 1)]
            if dmv > 0:
                span = (d09 - d01) / dmv

            pct_deriva = (np.sum(v_arr[d_arr < 150.0]) / vol_total) * 100.0
            pct_escorrimento = (np.sum(v_arr[d_arr > 600.0]) / vol_total) * 100.0

    return {
        "arquivo": uploaded_file.name,
        "otsu": int(limiar_otsu),
        "total_gotas": total_gotas,
        "densidade_cm2": densidade_gotas_cm2,
        "cobertura_pct": cobertura_pct,
        "dmv": dmv,
        "span": span,
        "deriva_pct": pct_deriva,
        "escorrimento_pct": pct_escorrimento
    }


def classificar_estrato(aplicacao, estrato, densidade_media, cobertura_media):
    regras = CRITERIOS_AGRONOMICOS[aplicacao][estrato]
    
    # Critério combinado: avalia densidade (gotas/cm²) e cobertura (%)
    if densidade_media >= regras["gotas_bom"] and cobertura_media >= regras["cob_bom"]:
        return "Adequado", "🟢", "success"
    elif densidade_media >= regras["gotas_aten"] and cobertura_media >= regras["cob_aten"]:
        return "Atenção", "🟡", "warning"
    else:
        return "Ruim / Insuficiente", "🔴", "error"


# ==============================================================================
# 🧭 CONTROLE DE ETAPAS (WIZARD) E BARRA LATERAL
# ==============================================================================
if "etapa" not in st.session_state:
    st.session_state.etapa = 1
if "cultura" not in st.session_state:
    st.session_state.cultura = "Soja"
if "aplicacao" not in st.session_state:
    st.session_state.aplicacao = "Fungicida"

# Barra Lateral: Calibração Física do Papel
st.sidebar.header("📏 Configuração do Papel")
tipo_papel = st.sidebar.selectbox(
    "Tamanho do Papel Hidrossensível",
    [
        "Papel Padrão (76 x 26 mm = 19.75 cm²)",
        "Amostra Quadrada (1.00 cm²)",
        "Personalizado (cm²)"
    ]
)

if "Personalizado" in tipo_papel:
    area_fisica_cm2 = st.sidebar.number_input("Área física do papel (cm²)", min_value=0.1, max_value=100.0, value=19.75, step=0.25)
elif "1.00" in tipo_papel:
    area_fisica_cm2 = 1.00
else:
    area_fisica_cm2 = 19.75

with st.sidebar.expander("⚙️ Ajustes Avançados de Imagem"):
    offset_otsu = st.slider("Ajuste Fino do Limiar Otsu (Offset)", -40, 40, 0, 1)
    usar_teto = st.checkbox("Descartar borrões gigantes (> 800 µm)", value=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reiniciar Diagnóstico"):
    st.session_state.etapa = 1
    st.rerun()

# Cabeçalho Principal
st.title("🌱 Spray Check — Diagnóstico de Pulverização")

# Barra de Progresso do Passo a Passo
progresso_map = {1: 0.33, 2: 0.66, 3: 1.0}
st.progress(progresso_map[st.session_state.etapa])

# ==============================================================================
# PASSO 1: ESCOLHA DA CULTURA
# ==============================================================================
if st.session_state.etapa == 1:
    st.subheader("Passo 1 de 3 — Qual é a cultura avaliada?")
    st.write("Selecione a cultura para carregar o esquema de arquitetura da planta:")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🌿 SOJA", use_container_width=True):
            st.session_state.cultura = "Soja"
            st.session_state.etapa = 2
            st.rerun()
    with c2:
        if st.button("🌽 MILHO", use_container_width=True):
            st.session_state.cultura = "Milho"
            st.session_state.etapa = 2
            st.rerun()
    with c3:
        if st.button("🌾 TRIGO", use_container_width=True):
            st.session_state.cultura = "Trigo"
            st.session_state.etapa = 2
            st.rerun()

# ==============================================================================
# PASSO 2: ESCOLHA DO TIPO DE APLICAÇÃO
# ==============================================================================
elif st.session_state.etapa == 2:
    st.info(f"Cultura selecionada: **{st.session_state.cultura}**")
    st.subheader("Passo 2 de 3 — Qual é o alvo / tipo de aplicação?")
    st.write("O tipo de produto define a exigência mínima de cobertura e gotas por $\\text{cm}^2$:")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🧪 Herbicida de Contato", use_container_width=True):
            st.session_state.aplicacao = "Herbicida de Contato"
            st.session_state.etapa = 3
            st.rerun()
        if st.button("🛡️ Fungicida", use_container_width=True):
            st.session_state.aplicacao = "Fungicida"
            st.session_state.etapa = 3
            st.rerun()

    with col_b:
        if st.button("🌱 Herbicida Sistêmico", use_container_width=True):
            st.session_state.aplicacao = "Herbicida Sistêmico"
            st.session_state.etapa = 3
            st.rerun()
        if st.button("🐛 Inseticida", use_container_width=True):
            st.session_state.aplicacao = "Inseticida"
            st.session_state.etapa = 3
            st.rerun()

    st.markdown("---")
    if st.button("⬅️ Voltar para Cultura"):
        st.session_state.etapa = 1
        st.rerun()

# ==============================================================================
# PASSO 3: LAYOUT DA PLANTA + UPLOADS POR ESTRATO + DIAGNÓSTICO FINAL
# ==============================================================================
elif st.session_state.etapa == 3:
    col_topo1, col_topo2 = st.columns([4, 1])
    with col_topo1:
        st.info(f"📋 **Configuração Ativa:** Cultura: **{st.session_state.cultura}** | Aplicação: **{st.session_state.aplicacao}** | Papel: **{area_fisica_cm2} cm²**")
    with col_topo2:
        if st.button("⬅️ Alterar Aplicação"):
            st.session_state.etapa = 2
            st.rerun()

    st.subheader(f"Passo 3 de 3 — Anexe os cartões nos pontos amostrados ({st.session_state.cultura})")
    st.caption("Você pode anexar uma ou mais fotos (repetições) em cada estrato. Se algum ponto não foi coletado (ex: Face Abaxial), basta deixar em branco.")

    col_planta, col_uploads = st.columns([1.1, 1.3])

    with col_planta:
        st.markdown(desenhar_planta_svg(st.session_state.cultura), unsafe_allow_html=True)

    with col_uploads:
        fotos_superior = st.file_uploader("1️⃣ Terço Superior", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="up_sup")
        fotos_medio    = st.file_uploader("2️⃣ Terço Médio", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="up_med")
        fotos_inferior = st.file_uploader("3️⃣ Terço Inferior", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="up_inf")
        fotos_abaxial  = st.file_uploader("4️⃣ Face Abaxial da Folha (Opcional)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="up_aba")

    st.markdown("---")
    if st.button("🔍 Analisar Pulverização e Gerar Diagnóstico", type="primary", use_container_width=True):
        estratos_map = [
            ("Terço Superior", fotos_superior),
            ("Terço Médio", fotos_medio),
            ("Terço Inferior", fotos_inferior),
            ("Face Abaxial", fotos_abaxial)
        ]

        total_fotos_enviadas = sum(len(lista) for _, lista in estratos_map)

        if total_fotos_enviadas == 0:
            st.warning("⚠️ Por favor, anexe pelo menos uma foto em algum dos estratos da planta antes de iniciar a análise.")
        else:
            st.subheader("📊 Diagnóstico Agronômico por Estrato")
            registros_excel = []

            for nome_estrato, lista_arquivos in estratos_map:
                if not lista_arquivos:
                    st.caption(f"⚪ **{nome_estrato}:** Não amostrado (ignorado na análise).")
                    continue

                resultados_estrato = []
                for arq in lista_arquivos:
                    res_foto = analisar_cartao(
                        arq,
                        area_fisica_cm2=area_fisica_cm2,
                        offset_otsu=offset_otsu,
                        usar_teto=usar_teto
                    )
                    resultados_estrato.append(res_foto)

                # Médias do estrato (caso haja mais de 1 cartão por terço)
                densidade_media = np.mean([r["densidade_cm2"] for r in resultados_estrato])
                cobertura_media = np.mean([r["cobertura_pct"] for r in resultados_estrato])
                dmv_medio       = np.mean([r["dmv"] for r in resultados_estrato])
                span_medio      = np.mean([r["span"] for r in resultados_estrato])
                deriva_media    = np.mean([r["deriva_pct"] for r in resultados_estrato])
                escorr_media    = np.mean([r["escorrimento_pct"] for r in resultados_estrato])

                status_texto, icone, tipo_alerta = classificar_estrato(
                    st.session_state.aplicacao,
                    nome_estrato,
                    densidade_media,
                    cobertura_media
                )

                # Exibição visual no estilo solicitado
                mensagem_principal = (
                    f"{icone} **{nome_estrato}: {status_texto}** — "
                    f"Cobertura de **{cobertura_media:.2f}%** com **{densidade_media:.1f} gotas/cm²** "
                    f"*(DMV: {dmv_medio:.1f} µm | Deriva <150µm: {deriva_media:.1f}% | Amostras: {len(lista_arquivos)})*"
                )

                if tipo_alerta == "success":
                    st.success(mensagem_principal)
                elif tipo_alerta == "warning":
                    st.warning(mensagem_principal)
                else:
                    st.error(mensagem_principal)

                # Salva cada foto individualmente na planilha para rastreabilidade completa
                for r in resultados_estrato:
                    registros_excel.append({
                        "Cultura": st.session_state.cultura,
                        "Aplicação": st.session_state.aplicacao,
                        "Estrato": nome_estrato,
                        "Diagnóstico Estrato": status_texto,
                        "Arquivo": r["arquivo"],
                        "Área Papel (cm²)": area_fisica_cm2,
                        "Limiar Otsu (Verde)": r["otsu"],
                        "Total Gotas": r["total_gotas"],
                        "Densidade (gotas/cm²)": round(r["densidade_cm2"], 1),
                        "Cobertura (%)": round(r["cobertura_pct"], 2),
                        "DMV (µm)": round(r["dmv"], 1),
                        "Span": round(r["span"], 2),
                        "Vol. Deriva <150µm (%)": round(r["deriva_pct"], 2),
                        "Vol. Escorrimento >600µm (%)": round(r["escorrimento_pct"], 2)
                    })

            # Exportação para Excel
            if registros_excel:
                st.markdown("---")
                df_diag = pd.DataFrame(registros_excel)
                with st.expander("📋 Ver Tabela Detalhada de Todas as Amostras"):
                    st.dataframe(df_diag, use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_diag.to_excel(writer, index=False, sheet_name='Spray_Check_Diagnostico')

                st.download_button(
                    label="📥 Baixar Laudo Completo em Excel (.xlsx)",
                    data=output.getvalue(),
                    file_name=f"spray_check_{st.session_state.cultura.lower()}_{st.session_state.aplicacao.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
