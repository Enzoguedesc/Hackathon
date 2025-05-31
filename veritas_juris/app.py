import streamlit as st
from dotenv import load_dotenv
import os
import time # For simulating delays if needed in mock functions

# --- Importar as funções do pipeline RAG ---
# Ensure rag_pipeline.py is in the same directory or PYTHONPATH
# and all these functions are correctly defined.
from rag_pipeline import (
    configure_llm,
    initialize_embedding_model,
    load_processes_from_original_json,
    process_documents_for_rag,
    create_vector_store,
    retrieve_relevant_chunks,
    generate_response_with_llm,
    mock_ai_analysis, # Make sure this is correctly defined
    mock_generate_argument_variations # Make sure this is correctly defined
)

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="VeritasJuris IA Pro",
    page_icon="veritas_juris/logo.png", # Changed icon for thematic relevance
    layout="wide",  
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'mailto:suporte@veritasjuris.ai', # Example
        'Report a bug': "mailto:bugs@veritasjuris.ai", # Example
        'About': """
         ## VeritasJuris IA Pro ⚖️

         **Versão:** 1.1 (Hackathon Edition Melhorada)

         **Desenvolvido para:** Hackathon IBMEC - Desafio de IA Generativa.

         ---

         **Objetivo:** Utilizar Inteligência Artificial Generativa para realizar análises avançadas e insights sobre jurisprudência, com foco inicial em Direito Tributário.

         **Funcionalidades Principais:**
         * Análise semântica de textos jurídicos.
         * Extração de resumos, palavras-chave e *ratio decidendi*.
         * "Tradução" de termos jurídicos para linguagem clara.
         * Geração de variações argumentativas.
         * Busca inteligente em base de jurisprudência.

         **Powered by Streamlit & Google Generative AI**
         """
    }
)

# --- Título Principal e Logo ---
col_title_logo, col_title_text = st.columns([1, 6])
with col_title_logo:
    # Replace with your actual logo URL or local path if preferred
    st.image("veritas_juris/logo.png", width=150) # Example logo
with col_title_text:
    st.title("VeritasJuris IA Pro")
    st.caption("Seu Assistente Jurídico Inteligente para Análise Avançada de Jurisprudência")

# --- Gerenciamento de Estado da Aplicação e Inicialização ---
if 'system_ready' not in st.session_state:
    st.session_state.system_ready = False
if 'embedding_model' not in st.session_state:
    st.session_state.embedding_model = None
if 'llm_model' not in st.session_state:
    st.session_state.llm_model = None
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
if 'all_chunks_ref' not in st.session_state:
    st.session_state.all_chunks_ref = []
if 'initial_documents' not in st.session_state:
    st.session_state.initial_documents = []

# --- Funções de Cache e Inicialização ---
@st.cache_resource
def load_models_cached():
    # Improved spinner message
    with st.spinner("🔄 Carregando e configurando modelos de IA (Embedding e LLM)... Por favor, aguarde."):
        embedding_model = initialize_embedding_model()
        llm_model = configure_llm()
    return embedding_model, llm_model

@st.cache_data # Changed to cache_data for data loading
def get_initial_documents_cached(data_file_path):
    if not os.path.exists(data_file_path):
        st.error(f"❌ Arquivo JSON principal não encontrado em: {data_file_path}")
        return []
    # Improved spinner message
    with st.spinner(f"📚 Carregando documentos base de '{os.path.basename(data_file_path)}'..."):
        docs = load_processes_from_original_json(data_file_path)
    return docs

@st.cache_resource
def prepare_rag_components_cached(_embedding_model, initial_documents):
    if not initial_documents:
        st.warning("⚠️ Nenhum documento inicial para processar. O índice RAG não será criado.")
        return None, []
    # Improved spinner message
    with st.spinner("⚙️ Processando documentos e construindo o índice vetorial para RAG..."):
        all_chunks = process_documents_for_rag(initial_documents)
        if not all_chunks:
            st.warning("⚠️ Nenhum chunk gerado a partir dos documentos. O índice RAG não será criado.")
            return None, []
        index, chunks_with_ids = create_vector_store(all_chunks, _embedding_model)
    return index, chunks_with_ids

def initialize_system():
    """Handles the initialization of models and RAG components."""
    try:
        st.session_state.embedding_model, st.session_state.llm_model = load_models_cached()
        # Ensure the path to your data file is correct
        data_file_path = os.path.join(os.path.dirname(__file__), "data", "processo.json")
        st.session_state.initial_documents = get_initial_documents_cached(data_file_path)

        if st.session_state.initial_documents:
            st.session_state.vector_store, st.session_state.all_chunks_ref = prepare_rag_components_cached(
                st.session_state.embedding_model, st.session_state.initial_documents
            )
            if st.session_state.vector_store and st.session_state.all_chunks_ref:
                st.session_state.system_ready = True
                # Using toast for a less intrusive "ready" message
                # st.toast("✅ Sistema RAG pronto para consultas!", icon="🚀") # Moved to after status
            else:
                st.error("⚠️ Falha ao preparar componentes RAG. O índice vetorial ou os chunks podem não ter sido criados.")
                st.session_state.system_ready = False
        else:
            st.error("⚠️ Documentos iniciais não foram carregados. O sistema RAG não pode ser inicializado.")
            st.session_state.system_ready = False

    except Exception as e:
        st.error(f"❌ Erro crítico durante a inicialização do sistema: {e}")
        st.exception(e) # Provides traceback for debugging
        st.session_state.system_ready = False
# --- Carregar Variáveis de Ambiente e Inicializar o Sistema ---
load_dotenv()




status_placeholder = st.empty()

if not st.session_state.get("system_ready", False):
    with status_placeholder.container():
        with st.spinner("⚙️ Carregando o sistema para pesquisa..."):
            initialize_system()
        if st.session_state.system_ready:
            with st.status("✅ Carregando o sistema para pesquisa", expanded=False) as status_bar:
                status_bar.update(label="✅ Sistema pronto!", state="complete", expanded=False)
                time.sleep(1)
                status_placeholder.empty()  # limpa o status da tela
        else:
            with st.status("⚠️ Falha na Inicialização. Verifique os erros acima.", expanded=True) as status_bar:
                status_bar.update(state="error")
else:
    status_placeholder.empty()

    
# --- ABAS PARA ORGANIZAR AS FUNCIONALIDADES ---
# Moved RAG query to the first tab as it's a primary feature
tab_rag, tab_analysis, tab_thesis, tab_advanced = st.tabs([
    "💬 Consulta à Base (RAG)",
    "📝 Análise de Texto Avulso",
    "💡 Explorador de Teses",
    "⚙️ Avançado & Exemplos"
])

with tab_rag:
    st.markdown("<h2 style='font-size: 32px;'>💬 Consulta Inteligente à Base de Jurisprudência</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 20px;'>Interaja com o acervo de jurisprudência carregado fazendo perguntas em linguagem natural.</p>", unsafe_allow_html=True)

    # Label customizada acima da text_area
    st.markdown("<label style='font-size: 18px; font-weight: bold;'>Digite sua pergunta sobre a jurisprudência carregada:</label>", unsafe_allow_html=True)

    query = st.text_area(
        label="",  # Remove o label nativo para usar o acima
        placeholder="Ex: Quais as implicações do RE XXXXX para a cobrança de ICMS sobre Y?",
        key="rag_query_input",
    )

    submit_rag_button = st.button(
        "⚖️ Buscar e Responder",
        type="primary",
        key="rag_submit",
        disabled=not st.session_state.system_ready,
        use_container_width=True
    )

    if not st.session_state.system_ready:
        st.warning("🔴 O Sistema de consulta à base (RAG) não está pronto ou falhou na inicialização. Funcionalidade indisponível.")

    if submit_rag_button and st.session_state.system_ready:
        if not query:
            st.warning("⚠️ Por favor, digite uma pergunta para iniciar a busca.")
        else:
            with st.spinner("🧠 Analisando sua pergunta e buscando respostas na base de dados..."):
                try:
                    relevant_chunks_data = retrieve_relevant_chunks(
                        query, st.session_state.vector_store, st.session_state.all_chunks_ref,
                        st.session_state.embedding_model, top_k=5
                    )
                    if not relevant_chunks_data:
                        # Provide feedback if no specific chunks are found
                        st.info("ℹ️ Não foram encontrados trechos altamente específicos para sua pergunta na base atual. A IA tentará fornecer uma resposta mais geral com base no conhecimento disponível.")

                    ai_response = generate_response_with_llm(query, relevant_chunks_data, st.session_state.llm_model)

                    st.subheader("💬 Resposta do VeritasJuris IA:")
                    st.markdown(ai_response) # Assuming markdown formatted response

                    if relevant_chunks_data:
                        st.divider()
                        st.subheader("📜 Documentos de Referência Consultados:")
                        # Use a set to avoid listing the same source document multiple times if different chunks came from it
                        processed_sources = set()
                        for chunk in relevant_chunks_data:
                            source_file = chunk["metadata_chunk"]["source_document"]
                            if source_file not in processed_sources:
                                original_doc = next((doc for doc in st.session_state.initial_documents if doc['source'] == source_file), None)
                                if original_doc:
                                    ementa = original_doc.get('ementa_display_text', 'Ementa não disponível.')
                                    doc_id = original_doc.get('id', 'ID não disponível')
                                    # Use an expander for each source for cleaner display
                                    with st.expander(f"📄 Fonte: {source_file} (ID do Documento: {doc_id})"):
                                        st.markdown(f"**Ementa:**\n {ementa}")
                                        # Optionally, display a snippet of the relevant chunk text
                                        # st.caption(f"Trecho Relevante do Chunk:\n...{chunk['text_chunk'][-200:]}...")
                                else:
                                    st.caption(f"⚠️ Detalhes do documento original não encontrados para: {source_file}")
                                processed_sources.add(source_file)
                except Exception as e:
                    st.error(f"❌ Erro ao processar a pergunta RAG: {e}")
                    st.exception(e) # Good for debugging



st.divider()
st.caption(f"VeritasJuris IA Pro v1.1 ✨ | Hackathon IBMEC | Streamlit v{st.__version__}")