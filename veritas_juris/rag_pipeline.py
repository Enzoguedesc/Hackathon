import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# rag_pipeline.py
import os
import json
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import google.generativeai as genai

# ... (mantenha configure_llm e initialize_embedding_model como estão) ...
# --- Configuração Inicial ---
def configure_llm():
    """Configura e retorna o cliente do LLM (ex: Google Gemini)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("API Key do Google não encontrada. Verifique o arquivo .env.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Ou outro modelo adequado
    return model

def initialize_embedding_model(model_name='paraphrase-multilingual-MiniLM-L12-v2'):
    """Inicializa e retorna o modelo de sentence transformer."""
    print(f"Carregando modelo de embedding: {model_name}...")
    model = SentenceTransformer(model_name)
    print("Modelo de embedding carregado.")
    return model

# --- NOVA LÓGICA DE CARREGAMENTO DE DADOS ---

def _extract_text_recursively(data_object):
    """
    Função auxiliar para extrair recursivamente todo o texto de um objeto JSON
    (dicionário, lista ou string).
    """
    text_parts = []
    if isinstance(data_object, dict):
        for key, value in data_object.items():
            # Ignorar chaves que não devem ser interpretadas como texto direto para concatenação,
            # como 'page', 'fileName', ou chaves que indicam apenas metadados não textuais.
            # Você pode refinar essa lista de chaves a serem ignoradas.
            if key not in ['page', 'fileName', 'document_signature_info', 'document_signature_info_page3', 
                           'document_signature_info_page4', 'document_signature_info_page5', 
                           'document_signature_info_page6', 'document_signature_info_page7', 
                           'document_signature_info_page8', 'document_signature_info_page9',
                           'document_signature_info_page10', 'document_signature_info_page11',
                           'document_signature_info_page12', 'document_signature_info_page13',
                           'document_signature_info_page14', 'document_signature_info_page15',
                           'document_signature_info_page16', 'document_footer', 'document_footer_page3', # etc.
                           'case_info_duplicate', 'parties_and_roles_duplicate', 'ementa_duplicate']: # Evitar duplicatas se houver
                text_parts.append(_extract_text_recursively(value))
    elif isinstance(data_object, list):
        for item in data_object:
            text_parts.append(_extract_text_recursively(item))
    elif isinstance(data_object, str):
        text_parts.append(data_object)
    # Ignorar outros tipos como números, booleanos, None

    return " ".join(filter(None, text_parts)).strip()

# rag_pipeline.py
import json
import os # Certifique-se de que 'os' está importado se ainda não estiver

# ... (outras importações e funções como configure_llm, initialize_embedding_model, etc.)

def load_processes_from_single_json(path_to_reformatted_json_file): # O parâmetro agora é o caminho para o NOVO arquivo JSON
    """
    MODIFICADO: Carrega dados do arquivo JSON que foi REFORMATADO 
    pelo script 'formatador_jurisprudencia.py'.
    O arquivo de entrada é uma lista de objetos, onde cada objeto tem
    "documentoOrigem" (com metadados) e "ementaProcessada" (com o texto da ementa).
    """
    documents_for_rag = [] # Lista para guardar os dados no formato que o restante do pipeline espera
    print(f"Carregando dados do arquivo JSON REFORMATADO: {path_to_reformatted_json_file}...")
    try:
        with open(path_to_reformatted_json_file, 'r', encoding='utf-8') as f:
            reformatted_data_list = json.load(f) # Espera-se uma lista

        if not isinstance(reformatted_data_list, list):
            print(f"ERRO: O arquivo JSON em {path_to_reformatted_json_file} não é uma lista na raiz.")
            return []

        for item_processado in reformatted_data_list:
            if not isinstance(item_processado, dict) or \
               "documentoOrigem" not in item_processado or \
               "ementaProcessada" not in item_processado:
                print(f"ALERTA: Item no JSON reformatado não tem a estrutura esperada (documentoOrigem/ementaProcessada): {item_processado}")
                continue

            doc_origem_metadata = item_processado.get("documentoOrigem", {})
            ementa_processada_data = item_processado.get("ementaProcessada", {})

            file_name_source = doc_origem_metadata.get("fileName", "FonteDesconhecida_" + str(len(documents_for_rag)))
            
            # O texto principal para o RAG (embeddings, contexto) virá do texto integral da ementa processada
            text_content_for_rag = ementa_processada_data.get("textoIntegralEmentaConcatenado", "")
            
            # O texto para exibir como "ementa" pode ser o mesmo ou um campo mais específico, se houver
            ementa_text_for_display = text_content_for_rag # Simplesmente usamos o mesmo por ora

            if text_content_for_rag.strip(): # Adiciona apenas se houver conteúdo de texto
                documents_for_rag.append({
                    "source": file_name_source,
                    "text": text_content_for_rag,  # Usado para chunking e embeddings
                    "ementa_display_text": ementa_text_for_display, # Usado no app.py para mostrar a ementa
                    "full_metadata_origem": doc_origem_metadata # Guarda todos os metadados originais
                })
            else:
                print(f"ALERTA: Ementa com texto vazio para '{file_name_source}' no arquivo reformatado.")
        
    except FileNotFoundError:
        print(f"ERRO: Arquivo JSON reformatado não encontrado em '{path_to_reformatted_json_file}'")
        return []
    except json.JSONDecodeError:
        print(f"ERRO: Falha ao decodificar o JSON reformatado em '{path_to_reformatted_json_file}'")
        return []
    except Exception as e:
        print(f"ERRO inesperado ao processar o JSON reformatado '{path_to_reformatted_json_file}': {e}")
        return []

    print(f"{len(documents_for_rag)} ementas carregadas e preparadas para RAG a partir do arquivo JSON reformatado.")
    return documents_for_rag

# As outras funções do rag_pipeline.py (chunk_text, process_documents_for_rag, 
# create_vector_store, retrieve_relevant_chunks, generate_response_with_llm)
# devem continuar funcionando bem, pois 'process_documents_for_rag' espera
# uma lista de dicionários com chaves "source" e "text", que é o que
# 'load_processes_from_single_json' (agora modificada) vai fornecer.

# --- Mantenha as funções chunk_text, process_documents_for_rag, ---
# --- create_vector_store, retrieve_relevant_chunks, ---
# --- e generate_response_with_llm como estavam, ---
# --- pois elas devem funcionar com a lista de 'documents' retornada. ---

# Exemplo de como process_documents_for_rag pode ser ajustado se necessário,
# mas ela já espera uma lista de {"source": ..., "text": ...}, que é o que a nova função retorna.
# Você apenas precisa garantir que os "text" sejam o conteúdo completo de cada processo.

# --- Etapa 2: Segmentação (Chunking) ---
def chunk_text(text, chunk_size=500, overlap=50): # chunk_size em palavras aproximadas
    """Segmenta um texto em pedaços menores."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    # Adicionar um filtro para remover chunks vazios ou muito pequenos se a segmentação resultar nisso
    return [chunk for chunk in chunks if chunk.strip()]


def process_documents_for_rag(documents_data):
    """
    Processa os documentos carregados: segmenta o texto de cada documento.
    Retorna uma lista de chunks com suas fontes.
    """
    all_chunks_with_source = []
    for doc_info in documents_data: # doc_info é {"source": "fileName.pdf", "text": "texto completo do processo"}
        source_file = doc_info.get("source", "FonteDesconhecida")
        full_text = doc_info.get("text", "")

        if not full_text.strip():
            print(f"Alerta: Documento da fonte '{source_file}' não possui conteúdo textual para processar.")
            continue

        text_chunks = chunk_text(full_text) # Segmenta o texto completo do processo
        
        for chunk_content in text_chunks:
            if chunk_content.strip(): # Garante que o chunk não é vazio
                all_chunks_with_source.append({"source": source_file, "text_chunk": chunk_content})

    if not all_chunks_with_source:
        print("Alerta: Nenhum chunk de texto foi gerado após o processamento e segmentação. Verifique os dados de entrada e a lógica de extração/segmentação.")

    print(f"Total de {len(all_chunks_with_source)} chunks de texto criados após segmentação.")
    return all_chunks_with_source


# --- Etapa 3 e 4: Geração de Embeddings e Criação do Vector Store (FAISS) ---
def create_vector_store(text_chunks_with_source, embedding_model):
    """
    Gera embeddings para os chunks de texto e cria um índice FAISS.
    Retorna o índice FAISS e a lista de chunks (para referência).
    """
    if not text_chunks_with_source:
        print("Nenhum chunk de texto fornecido para criar o vector store.")
        return None, []

    valid_chunks_with_source = [chunk for chunk in text_chunks_with_source if chunk.get("text_chunk", "").strip()]

    if not valid_chunks_with_source:
        print("Nenhum chunk de texto válido encontrado após filtragem para o vector store.")
        return None, []

    texts_to_embed = [chunk["text_chunk"] for chunk in valid_chunks_with_source]

    print(f"Gerando embeddings para {len(texts_to_embed)} chunks de texto...")
    embeddings = embedding_model.encode(texts_to_embed, show_progress_bar=True)
    print("Embeddings gerados.")

    if embeddings.ndim == 1:
        embeddings = np.expand_dims(embeddings, axis=0)
    if embeddings.shape[0] == 0:
        print("Nenhum embedding foi gerado. O Vector Store não pode ser criado.")
        return None, []

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    print(f"Vector store FAISS criado com {index.ntotal} vetores.")
    return index, valid_chunks_with_source

# --- Etapa 5: Recuperação (Retrieval) ---
def retrieve_relevant_chunks(query, vector_store_index, text_chunks_list, embedding_model, top_k=3):
    """
    Busca os chunks de texto mais relevantes para a query no vector store.
    """
    if vector_store_index is None or vector_store_index.ntotal == 0:
        print("Vector store não inicializado ou vazio. Não é possível fazer a busca.")
        return []
    if not query:
        print("Query vazia. Não é possível fazer a busca.")
        return []

    print(f"Gerando embedding para a query: '{query}'")
    query_embedding = embedding_model.encode([query])
    if query_embedding.ndim == 1:
        query_embedding = np.expand_dims(query_embedding, axis=0)

    print(f"Buscando {top_k} chunks mais relevantes...")
    distances, indices = vector_store_index.search(query_embedding.astype('float32'), top_k)

    relevant_chunks = []
    for i in range(len(indices[0])):
        idx = indices[0][i]
        if 0 <= idx < len(text_chunks_list):
            relevant_chunks.append(text_chunks_list[idx])
        else:
            print(f"Alerta: Índice {idx} fora do intervalo da lista de chunks (tamanho: {len(text_chunks_list)}).")

    print(f"{len(relevant_chunks)} chunks relevantes encontrados.")
    return relevant_chunks

# --- Etapa 6: Geração da Resposta com LLM ---
def generate_response_with_llm(query, relevant_chunks, llm_model):
    if not relevant_chunks:
        # Se não houver chunks, o LLM pode ser instruído a dizer que não encontrou info,
        # ou você pode retornar uma mensagem padrão aqui.
        # O prompt abaixo já lida com isso.
        context_from_chunks = "Nenhuma informação específica encontrada nos documentos para esta pergunta."
    else:
        context_from_chunks = "\n\n---\n\n".join([chunk["text_chunk"] for chunk in relevant_chunks])

    prompt = f"""
    Você é VeritasJuris, um assistente de IA especializado em Direito Tributário brasileiro.
    Sua tarefa é responder à pergunta do usuário de forma clara, concisa e fundamentada EXCLUSIVAMENTE
    nas informações contidas nos seguintes trechos de jurisprudência.
    Não utilize conhecimento externo. Se a informação não estiver nos trechos, diga que não pode responder com base no material fornecido.

    TRECHOS DA JURISPRUDÊNCIA (use estes para basear sua resposta):
    {context_from_chunks}

    PERGUNTA DO USUÁRIO:
    {query}

    RESPOSTA FUNDAMENTADA:
    """
    print("Gerando resposta com LLM (baseado em chunks)...")
    try:
        response = llm_model.generate_content(prompt)
        # print(f"DEBUG: Prompt enviado ao LLM para resposta principal:\n{prompt}\n") # Descomente para depurar
        print("Resposta gerada.")
        return response.text
    except Exception as e:
        print(f"Erro ao gerar resposta com o LLM: {e}")
        return "Ocorreu um erro ao tentar gerar a resposta principal. Por favor, tente novamente."
    
    