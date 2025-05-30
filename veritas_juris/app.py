import streamlit as st
from dotenv import load_dotenv
import os

# Importar as funções do seu pipeline RAG (ajustado)
from rag_pipeline import (
    configure_llm,
    initialize_embedding_model,
    load_processes_from_original_json, # <<< ATUALIZADO para a função que lê o JSON original
    process_documents_for_rag,
    create_vector_store,
    retrieve_relevant_chunks,
    generate_response_with_llm
)

# --- 1. Configuração da Página e Setup Inicial ---
st.set_page_config(page_title="VeritasJuris IA", layout="wide", initial_sidebar_state="expanded")
st.title("⚖️ VeritasJuris IA - Análise de Jurisprudência")

# Carregar variáveis de ambiente
load_dotenv()

# --- 2. Funções Cacheadas para Carregar Modelos e Dados ---

@st.cache_resource
def load_models_cached():
    """Carrega o modelo de embedding e configura o LLM."""
    st.write("Carregando modelos (embedding e LLM)...")
    embedding_model = initialize_embedding_model()
    llm_model = configure_llm()
    st.write("Modelos carregados com sucesso!")
    return embedding_model, llm_model

@st.cache_data # Mudei para @st.cache_data para a lista de documentos, pois não são "recursos" como modelos
def get_initial_documents_cached(data_file_path):
    """Carrega os documentos do JSON original e retorna a lista para referência."""
    if not os.path.exists(data_file_path):
        st.error(f"Arquivo JSON principal não encontrado em: {data_file_path}.")
        return []
    # Usa a função do rag_pipeline que agora lê o JSON original
    # Esta função retorna uma lista de dicionários com "source", "text", "ementa_display_text", "full_metadata_origem"
    loaded_docs = load_processes_from_original_json(data_file_path)
    if not loaded_docs:
         st.warning("Nenhum documento foi carregado do arquivo JSON original.")
    return loaded_docs

@st.cache_resource # Vector store é um recurso
def prepare_rag_components_cached(_embedding_model_ref, initial_documents):
    """Prepara os componentes do RAG: chunks e vector store."""
    if not initial_documents:
        st.warning("Nenhum documento inicial fornecido para preparar os componentes RAG.")
        return None, []

    st.write("Processando documentos para RAG (chunking)...")
    # A função process_documents_for_rag espera a lista de initial_documents
    # que já tem "source" e "text" (texto completo)
    all_chunks_with_metadata = process_documents_for_rag(initial_documents)
    if not all_chunks_with_metadata:
        st.warning("Nenhum chunk de texto foi gerado. Verifique os dados e a lógica de segmentação.")
        return None, []

    st.write("Criando vector store...")
    vector_store_index, chunks_for_retrieval_with_metadata = create_vector_store(all_chunks_with_metadata, _embedding_model_ref)

    if vector_store_index is None:
        st.error("Falha ao criar o Vector Store.")
    else:
        st.write(f"Base de conhecimento RAG carregada com {len(chunks_for_retrieval_with_metadata)} chunks.")
    # Retorna o índice e a lista de chunks com metadados, que inclui o texto do chunk e os metadados associados
    return vector_store_index, chunks_for_retrieval_with_metadata


# --- 3. Carregar Modelos e Dados na Inicialização do App ---
embedding_model_global = None
llm_global = None
vector_store_global = None
# `all_chunks_ref_global` agora armazena os chunks com seus metadados associados
all_chunks_ref_global = []
# `initial_documents_global` armazena os documentos originais carregados com "source", "text", "ementa_display_text"
initial_documents_global = []

try:
    embedding_model_global, llm_global = load_models_cached()

    # Caminho para o SEU ÚNICO arquivo JSON original
    # Certifique-se de que este arquivo JSON está na pasta 'data'
    # Substitua 'SEU_ARQUIVO_JSON_COMPLETO.json' pelo nome real do seu arquivo.
    data_file_path = os.path.join(os.path.dirname(__file__), "data", "processo.json")

    initial_documents_global = get_initial_documents_cached(data_file_path)

    if initial_documents_global: # Só prepara o RAG se os documentos foram carregados
        vector_store_global, all_chunks_ref_global = prepare_rag_components_cached(embedding_model_global, initial_documents_global)
    else:
        st.error("Não foi possível carregar os documentos iniciais. O pipeline RAG não pode ser preparado.")

except Exception as e:
    st.error(f"Erro crítico durante a inicialização dos modelos ou dados: {e}")
    st.error("Verifique sua chave de API, a conexão com a internet e os arquivos de dados. Veja o console para mais detalhes.")
    # st.stop() # Descomente se quiser parar o app em caso de falha total

# --- 4. Interface do Usuário ---

st.sidebar.header("Sobre o VeritasJuris IA")
st.sidebar.info(
    "Esta aplicação demonstra o uso de Inteligência Artificial Generativa (RAG) "
    "para analisar jurisprudências. Faça uma pergunta sobre o conteúdo "
    "dos documentos JSON carregados."
)
st.sidebar.warning("⚠️ Lembre-se: Esta é uma ferramenta de demonstração para o Hackathon Ibmec e não substitui a consultoria jurídica profissional.")

# Exibir informações sobre os dados carregados
if initial_documents_global:
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"Documentos Carregados na Base:")
    st.sidebar.caption(f"{len(initial_documents_global)} documento(s) principal(is) carregado(s) de:")
    st.sidebar.code(os.path.basename(data_file_path), language=None)
    if all_chunks_ref_global:
        st.sidebar.caption(f"Gerados {len(all_chunks_ref_global)} chunks para busca.")
    else:
        st.sidebar.caption("Nenhum chunk gerado (verifique logs).")
else:
    st.sidebar.markdown("---")
    st.sidebar.caption("Base de conhecimento (documentos) não carregada ou vazia.")
    st.warning("A base de conhecimento não pôde ser carregada. Verifique as mensagens de erro e o console.")

st.markdown("---")
query = st.text_input("Digite sua pergunta sobre a jurisprudência carregada:", placeholder="Ex: Quais as implicações do RE XXXXX para a cobrança de ICMS sobre Y?")

if st.button("Analisar e Responder", type="primary"):
    if not query:
        st.warning("Por favor, digite uma pergunta.")
    elif vector_store_global is None or not all_chunks_ref_global or not initial_documents_global:
        st.error("O sistema não está pronto para responder. A base de conhecimento não foi carregada ou processada corretamente.")
    else:
        with st.spinner("Buscando informações na jurisprudência e gerando sua resposta..."):
            try:
                # retrieve_relevant_chunks agora usa all_chunks_ref_global, que são os chunks com metadados
                relevant_chunks_data = retrieve_relevant_chunks(query, vector_store_global, all_chunks_ref_global, embedding_model_global, top_k=5) # Aumentei top_k para teste

                # 1. GERAR E EXIBIR A RESPOSTA PRINCIPAL DA IA
                ai_response = generate_response_with_llm(query, relevant_chunks_data, llm_global)
                st.subheader("Resposta do VeritasJuris IA:")
                st.markdown(ai_response)

                # 2. EXIBIR AS EMENTAS DOS JULGADOS DE REFERÊNCIA
                if relevant_chunks_data:
                    st.markdown("---")
                    st.subheader("Ementas dos Documentos de Referência Citados:")

                    # Coleta os nomes dos arquivos fontes dos chunks relevantes
                    source_files_from_chunks = list(set(chunk_data["metadata_chunk"]["source_document"] for chunk_data in relevant_chunks_data))

                    if not source_files_from_chunks:
                        st.caption("Nenhuma fonte específica identificada nos chunks relevantes para exibir ementas.")
                    else:
                        displayed_ementas_count = 0
                        for source_file_name in source_files_from_chunks:
                            # Encontra o documento original na lista `initial_documents_global`
                            # para pegar o `ementa_display_text` que foi extraído pela `load_processes_from_original_json`
                            original_doc_for_ementa = next((doc for doc in initial_documents_global if doc['source'] == source_file_name), None)

                            if original_doc_for_ementa:
                                ementa_text = original_doc_for_ementa.get('ementa_display_text')
                                if ementa_text and ementa_text != "Ementa não encontrada.":
                                    with st.expander(f"Ver Ementa de: {source_file_name}", expanded=False):
                                        st.markdown(ementa_text)
                                    displayed_ementas_count += 1
                                else:
                                    with st.expander(f"Informações sobre: {source_file_name}", expanded=False):
                                        st.caption(f"Ementa principal não encontrada ou não disponível para {source_file_name} durante o carregamento.")
                            else:
                                 st.caption(f"Metadados do documento original '{source_file_name}' não encontrados na lista `initial_documents_global`.")
                        
                        if displayed_ementas_count == 0 and source_files_from_chunks:
                            st.caption("Ementas não disponíveis para os documentos referenciados ou não foram extraídas corretamente.")


                    st.markdown("---")

                # 3. OPCIONAL: MANTER O EXPANDER DOS CHUNKS DETALHADOS
                if relevant_chunks_data:
                    with st.expander("Ver Trechos Detalhados Consultados (Chunks)"):
                        for i, chunk_data_detail in enumerate(relevant_chunks_data):
                            # chunk_data_detail agora é o objeto completo do chunk, incluindo seus metadados
                            st.write(f"**Trecho {i+1} (Fonte: {chunk_data_detail['metadata_chunk']['source_document']})**")
                            st.caption(f"Texto do Chunk: {chunk_data_detail['text_chunk']}")
                            # Você pode optar por mostrar outros metadados do chunk aqui, se desejar
                            # st.json(chunk_data_detail['metadata_chunk']) # Para depuração
                            st.markdown("---")

            except Exception as e:
                st.error(f"Ocorreu um erro ao processar sua solicitação: {e}")
                st.exception(e) # Mostra o traceback completo no Streamlit para depuração
                st.error("Por favor, verifique o console para mais detalhes técnicos.")

st.markdown("---")
st.caption("Hackathon Ibmec - Desafio de IA Generativa - VeritasJuris")