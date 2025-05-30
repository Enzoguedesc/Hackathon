import streamlit as st
from dotenv import load_dotenv
import os

# Importar as funções do seu pipeline RAG
# Certifique-se de que o arquivo rag_pipeline.py está na mesma pasta que app.py
from rag_pipeline import (
    configure_llm,
    initialize_embedding_model,
    # REMOVA: load_json_from_directory (se você a removeu do rag_pipeline.py)
    load_processes_from_single_json, # ADICIONE esta nova função
    process_documents_for_rag,
    create_vector_store,
    retrieve_relevant_chunks,
    generate_response_with_llm
)

# --- 1. Configuração da Página e Setup Inicial ---
st.set_page_config(page_title="VeritasJuris IA", layout="wide", initial_sidebar_state="expanded")
st.title("⚖️ VeritasJuris IA - Análise de Jurisprudência Tributária")

# Carregar variáveis de ambiente (para API keys)
load_dotenv() # Garanta que você tem um arquivo .env com sua GOOGLE_API_KEY

# --- 2. Funções Cacheadas para Carregar Modelos e Dados ---
# Estas funções só rodarão uma vez e seus resultados serão armazenados em cache
# Isso é essencial para a performance, especialmente em um hackathon.

@st.cache_resource # Cacheia o objeto do modelo real
def load_models_cached():
    """Carrega o modelo de embedding e configura o LLM."""
    st.write("Carregando modelos (embedding e LLM)...") # Feedback para o usuário
    embedding_model = initialize_embedding_model() # Função do rag_pipeline.py
    llm_model = configure_llm() # Função do rag_pipeline.py
    st.write("Modelos carregados com sucesso!")
    return embedding_model, llm_model

@st.cache_resource
def load_and_prepare_data_cached(_embedding_model_ref):
    st.write("Carregando e processando o arquivo JSON único...")
    
    # Caminho para o SEU ÚNICO arquivo JSON dentro da pasta data/
    # Certifique-se de que este arquivo JSON está na pasta 'data'
    # E substitua 'SEU_ARQUIVO_JSON_UNICO.json' pelo nome real do seu arquivo.
    data_file_path = os.path.join(os.path.dirname(__file__), "data", "processo.json") 

    if not os.path.exists(data_file_path):
        st.error(f"Arquivo JSON principal não encontrado em: {data_file_path}. Verifique o nome e o local do arquivo na pasta 'data'.")
        return None, []

    # Chama a nova função de carregamento
    documents_data = load_processes_from_single_json(data_file_path)
    
    if not documents_data:
        st.warning("Nenhum processo foi carregado do arquivo JSON. Verifique a estrutura do arquivo e os logs no console.")
        return None, []

    all_chunks_with_source = process_documents_for_rag(documents_data)
    if not all_chunks_with_source:
        st.warning("Nenhum chunk de texto foi gerado a partir dos processos. Verifique o conteúdo do JSON e a lógica de extração/segmentação.")
        return None, []

    vector_store_index, text_chunks_for_retrieval = create_vector_store(all_chunks_with_source, _embedding_model_ref)

    if vector_store_index is None:
        st.error("Falha ao criar o Vector Store. Verifique os logs no console e os dados de entrada.")
    else:
        st.write(f"Base de conhecimento carregada com {len(text_chunks_for_retrieval)} chunks de texto.")
    return vector_store_index, text_chunks_for_retrieval

# --- 3. Carregar Modelos e Dados na Inicialização do App ---
# As funções cacheadas acima serão chamadas aqui.
try:
    embedding_model_global, llm_global = load_models_cached()
    # Passamos o embedding_model_global para garantir a ordem correta de execução e uso do cache
    vector_store_global, text_chunks_global = load_and_prepare_data_cached(embedding_model_global)
    # Carregar os documentos originais para uso posterior (ex: exibir ementas)
    # Reutiliza a mesma lógica de carregamento do JSON único
    data_file_path = os.path.join(os.path.dirname(__file__), "data", "processo.json")
    if os.path.exists(data_file_path):
        initial_loaded_documents_global = load_processes_from_single_json(data_file_path)
    else:
        initial_loaded_documents_global = []
except Exception as e:
    st.error(f"Erro crítico durante a inicialização dos modelos ou dados: {e}")
    st.error("Verifique sua chave de API, a conexão com a internet e os arquivos de dados. Veja o console para mais detalhes.")
    st.stop() # Interrompe a execução do app se a inicialização falhar

# --- 4. Interface do Usuário ---

st.sidebar.header("Sobre o VeritasJuris IA")
st.sidebar.info(
    "Esta aplicação demonstra o uso de Inteligência Artificial Generativa (RAG) "
    "para analisar jurisprudências de Direito Tributário. Faça uma pergunta sobre o conteúdo "
    "dos documentos JSON carregados na pasta 'data'."
)
st.sidebar.warning("⚠️ Lembre-se: Esta é uma ferramenta de demonstração para o Hackathon Ibmec e não substitui a consultoria jurídica profissional.")

# Exibir informações sobre os dados carregados
if text_chunks_global:
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"Base de Conhecimento Ativa:")
    unique_sources = sorted(list(set(chunk['source'] for chunk in text_chunks_global if 'source' in chunk)))
    if unique_sources:
        st.sidebar.caption(f"{len(unique_sources)} arquivo(s) JSON da pasta 'data':")
        for source_file in unique_sources:
            st.sidebar.code(source_file, language=None) # Mostra o nome do arquivo
    else:
        st.sidebar.caption("Nenhum arquivo fonte identificado nos chunks.")
else:
    st.sidebar.markdown("---")
    st.sidebar.caption("Base de conhecimento não carregada ou vazia.")
    st.warning("A base de conhecimento (arquivos JSON na pasta 'data') não pôde ser carregada. Verifique as mensagens de erro e o console.")

st.markdown("---")
query = st.text_input("Digite sua pergunta sobre a jurisprudência tributária carregada:", placeholder="Ex: Quais as implicações do RE XXXXX para a cobrança de ICMS sobre Y?")

# app.py
# ... (dentro da lógica do botão "Analisar e Responder") ...
if st.button("Analisar e Responder", type="primary"):
    if not query:
        st.warning("Por favor, digite uma pergunta.")
    elif vector_store_global is None or not text_chunks_global or not initial_loaded_documents_global: # Adicionado initial_loaded_documents_global na verificação
        st.error("O sistema não está pronto para responder. A base de conhecimento não foi carregada corretamente.")
    else:
        with st.spinner("Buscando informações na jurisprudência e gerando sua resposta..."):
            try:
                relevant_chunks_data = retrieve_relevant_chunks(query, vector_store_global, text_chunks_global, embedding_model_global, top_k=3)
                
                # 1. GERAR E EXIBIR A RESPOSTA PRINCIPAL DA IA PRIMEIRO
                ai_response = generate_response_with_llm(query, relevant_chunks_data, llm_global)
                st.subheader("Resposta do VeritasJuris IA:")
                st.markdown(ai_response)

                # 2. EXIBIR AS EMENTAS DOS JULGADOS DE REFERÊNCIA APÓS A RESPOSTA
                if relevant_chunks_data:
                    st.markdown("---") 
                    st.subheader("Ementas dos Julgados de Referência:")
                    
                    unique_sources_for_ementa_display = set()
                    for chunk_info_for_ementa in relevant_chunks_data:
                        source_file_for_ementa = chunk_info_for_ementa['source']
                        if source_file_for_ementa not in unique_sources_for_ementa_display:
                            original_doc_for_ementa = next((doc for doc in initial_loaded_documents_global if doc['source'] == source_file_for_ementa), None)
                            if original_doc_for_ementa and original_doc_for_ementa.get('ementa_text'):
                                with st.expander(f"Ver Ementa de: {source_file_for_ementa}", expanded=False): # Começa fechado
                                    st.markdown(original_doc_for_ementa['ementa_text'])
                                unique_sources_for_ementa_display.add(source_file_for_ementa)
                    st.markdown("---")

                # 3. OPCIONAL: MANTER O EXPANDER DOS CHUNKS DETALHADOS (se ainda quiser)
                if relevant_chunks_data:
                    with st.expander("Ver Trechos Detalhados Consultados (Chunks)"):
                        for i, chunk_info_detail in enumerate(relevant_chunks_data):
                            st.write(f"**Trecho {i+1} (Fonte: {chunk_info_detail['source']})**")
                            st.caption(chunk_info_detail['text_chunk'])
                            st.markdown("---")

            except Exception as e:
                st.error(f"Ocorreu um erro ao processar sua solicitação: {e}")
                st.error("Por favor, verifique o console para mais detalhes técnicos.")

st.markdown("---")
st.caption("Hackathon Ibmec 2025 - Desafio de IA Generativa - VeritasJuris")