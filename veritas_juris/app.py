import streamlit as st
from dotenv import load_dotenv
import os

# Importar as funções do pipeline RAG
from rag_pipeline import (
    configure_llm,
    initialize_embedding_model,
    load_processes_from_original_json,
    process_documents_for_rag,
    create_vector_store,
    retrieve_relevant_chunks,
    generate_response_with_llm,
    mock_ai_analysis,
    mock_generate_argument_variations
)

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="VeritasJuris IA Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': """
        ## VeritasJuris IA Pro ⚖️
        **Versão:** 1.0 (Hackathon Edition)
        **Desenvolvido para:** Hackathon IBMEC - Desafio de IA Generativa.
        Utiliza IA para análise avançada de jurisprudência tributária.
        """
    }
)

# --- Sidebar ---
with st.sidebar:
    st.header("Painel de Controle")

    st.subheader("1. Insira a Jurisprudência")
    jurisprudence_source = st.radio(
        "Origem do texto:",
        ("Colar Texto", "Carregar Arquivo TXT (em breve)"),
        key="source_select"
    )

    jurisprudence_text_area = ""
    if jurisprudence_source == "Colar Texto":
        jurisprudence_text_area = st.text_area(
            "Cole o texto completo da decisão/acórdão aqui:",
            height=250,
            placeholder="Ex: EMENTA: HABEAS CORPUS. PACIENTE PRESO PREVENTIVAMENTE..."
        )
    else:
        st.info("Funcionalidade de upload de arquivo será implementada em breve.")

    analyze_button = st.button("🔍 Analisar Jurisprudência", type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("2. Explore Teses (Opcional)")
    user_thesis = st.text_input("Insira sua tese ou ponto principal para explorar variações:")
    explore_thesis_button = st.button("💡 Explorar Variações da Tese", use_container_width=True)

# --- Análise de Jurisprudência ---
if analyze_button and jurisprudence_text_area:
    with st.spinner("🤖 A IA está analisando a jurisprudência... Por favor, aguarde."):
        summary, keywords, ratio, simplified = mock_ai_analysis(jurisprudence_text_area)

    if summary:
        st.subheader("📊 Resultados da Análise da IA:")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📜 Resumo Inteligente")
            st.success(summary)

            st.markdown("#### 🔑 Palavras-chave e Teses Centrais")
            if keywords:
                cols_keywords = st.columns(min(4, len(keywords)))
                for i, keyword in enumerate(keywords):
                    cols_keywords[i % 4].info(f"🏷️ {keyword}")
            else:
                st.write("Nenhuma palavra-chave identificada.")

        with col2:
            st.markdown("#### 🎯 Ratio Decidendi (Razão de Decidir)")
            st.info(ratio)

            st.markdown("#### 🗣️ 'Tradução' para Linguagem Clara")
            st.warning(simplified)

        st.markdown("---")
        st.subheader("❓ Pergunte sobre a Jurisprudência (Demonstração)")
        user_question = st.text_input("Faça uma pergunta específica sobre o texto analisado:")
        if user_question:
            st.write(f"**Resposta da IA (simulada):** Para a pergunta '{user_question}', a análise sugere que [resposta simulada baseada no texto e na IA].")

elif analyze_button:
    st.warning("Por favor, cole o texto da jurisprudência na área indicada antes de analisar.")

# --- Variações da Tese ---
if explore_thesis_button:
    if user_thesis:
        with st.spinner("🧠 A IA está gerando variações da tese..."):
            variations = mock_generate_argument_variations(user_thesis)
        if variations:
            st.subheader(f"💡 Variações e Contrapontos para '{user_thesis}':")
            for i, var in enumerate(variations):
                st.info(f"**Opção {i+1}:** {var}")
        else:
            st.info("Nenhuma variação gerada. Tente uma tese mais específica.")
    else:
        st.warning("Por favor, insira uma tese para explorar.")

# --- Expansão: Grafo ---
st.subheader("✨ Funcionalidades Avançadas (Em Desenvolvimento)")
with st.expander("🗺️ Visualizar Conexões Jurisprudenciais (Exemplo)"):
    st.write("Esta seção demonstraria como diferentes decisões se conectam.")
    try:
        st.graphviz_chart('''
            digraph {
                rankdir=LR;
                node [shape=box, style="filled", color="skyblue"];
                edge [color="gray40"];
                acordao_A [label="Acórdão A\nTema Principal"];
                acordao_B [label="Acórdão B\nCita Acórdão A"];
                acordao_C [label="Acórdão C\nDistingue de A"];
                acordao_A -> acordao_B [label=" citado por"];
                acordao_A -> acordao_C [label=" distinguido por"];
            }
        ''')
    except Exception as e:
        st.caption(f"Erro ao exibir o grafo: {e}")
    st.caption("Imagine aqui um grafo interativo mostrando as relações entre decisões analisadas!")

# --- Carregar Variáveis de Ambiente ---
load_dotenv()

# --- Cache de Modelos e Dados ---
@st.cache_resource
def load_models_cached():
    embedding_model = initialize_embedding_model()
    llm_model = configure_llm()
    return embedding_model, llm_model

@st.cache_data
def get_initial_documents_cached(data_file_path):
    if not os.path.exists(data_file_path):
        st.error(f"Arquivo JSON principal não encontrado: {data_file_path}")
        return []
    return load_processes_from_original_json(data_file_path)

@st.cache_resource
def prepare_rag_components_cached(embedding_model, initial_documents):
    if not initial_documents:
        return None, []
    all_chunks = process_documents_for_rag(initial_documents)
    if not all_chunks:
        return None, []
    index, chunks = create_vector_store(all_chunks, embedding_model)
    return index, chunks

# --- Inicialização ---
embedding_model_global, llm_global = None, None
vector_store_global, all_chunks_ref_global = None, []
initial_documents_global = []

try:
    embedding_model_global, llm_global = load_models_cached()
    data_file_path = os.path.join(os.path.dirname(__file__), "data", "processo.json")
    initial_documents_global = get_initial_documents_cached(data_file_path)

    if initial_documents_global:
        vector_store_global, all_chunks_ref_global = prepare_rag_components_cached(
            embedding_model_global, initial_documents_global
        )
    else:
        st.error("Documentos iniciais não foram carregados corretamente.")

except Exception as e:
    st.error(f"Erro na inicialização: {e}")

# --- Interface de Pergunta ---
st.markdown("---")
query = st.text_input("Digite sua pergunta sobre a jurisprudência carregada:",
                      placeholder="Ex: Quais as implicações do RE XXXXX para a cobrança de ICMS sobre Y?")

if st.button("Analisar e Responder", type="primary"):
    if not query:
        st.warning("Por favor, digite uma pergunta.")
    elif not vector_store_global or not all_chunks_ref_global:
        st.error("Sistema ainda não está pronto. Verifique o carregamento inicial.")
    else:
        with st.spinner("Analisando e buscando respostas..."):
            try:
                relevant_chunks_data = retrieve_relevant_chunks(
                    query, vector_store_global, all_chunks_ref_global,
                    embedding_model_global, top_k=5
                )
                ai_response = generate_response_with_llm(query, relevant_chunks_data, llm_global)
                st.subheader("Resposta do VeritasJuris IA:")
                st.markdown(ai_response)

                if relevant_chunks_data:
                    st.markdown("---")
                    st.subheader("Ementas dos Documentos de Referência Citados:")
                    source_files = list(set(chunk["metadata_chunk"]["source_document"] for chunk in relevant_chunks_data))

                    for file_name in source_files:
                        original_doc = next((doc for doc in initial_documents_global if doc['source'] == file_name), None)
                        if original_doc:
                            ementa = original_doc.get('ementa_display_text', '')
                            if ementa and ementa != "Ementa não encontrada.":
                                with st.expander(f"Ver Ementa de: {file_name}"):
                                    st.markdown(ementa)
                            else:
                                st.caption(f"Ementa não disponível para: {file_name}")
                        else:
                            st.caption(f"Documento original não encontrado: {file_name}")
            except Exception as e:
                st.error(f"Erro ao processar a pergunta: {e}")
