# rag_pipeline.py
import os
import json
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import google.generativeai as genai

# --- Configuração Inicial (sem alterações) ---
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

# --- LÓGICA DE EXTRAÇÃO DE TEXTO (mantida a sua função) ---
def _extract_text_recursively(data_object):
    """
    Função auxiliar para extrair recursivamente todo o texto de um objeto JSON
    (dicionário, lista ou string).
    """
    text_parts = []
    if isinstance(data_object, dict):
        for key, value in data_object.items():
            # Ignorar chaves que não devem ser interpretadas como texto direto para concatenação
            # ou chaves que indicam apenas metadados não textuais.
            # A lista de chaves ignoradas pode ser refinada.
            ignored_keys = [
                'page', 'fileName', 'document_signature_info', 'document_signature_info_page3',
                'document_signature_info_page4', 'document_signature_info_page5',
                'document_signature_info_page6', 'document_signature_info_page7',
                'document_signature_info_page8', 'document_signature_info_page9',
                'document_signature_info_page10', 'document_signature_info_page11',
                'document_signature_info_page12', 'document_signature_info_page13',
                'document_signature_info_page14', 'document_signature_info_page15',
                'document_signature_info_page16', 'document_footer', 'document_footer_page3',
                'case_info_duplicate', 'parties_and_roles_duplicate', 'ementa_duplicate', # Evitar duplicatas
                'control_code', 'law_reference', # Campos de assinatura geralmente não são texto principal
                # Chaves que são claramente metadados e não conteúdo textual principal para RAG
                'numero_registro', 'numero_origem', 'sessao_virtual', 'relator_agint', 'presidente_sessao',
                'title', # Se o título for apenas "EMENTA", "ACÓRDÃO", etc., pode ser redundante se o corpo for extraído.
                        # Mas se o title tiver conteúdo útil, reavalie.
            ]
            # Condição especial para 'ementa' se quisermos um tratamento diferente ou já foi pego
            if key not in ignored_keys:
                text_parts.append(_extract_text_recursively(value))
    elif isinstance(data_object, list):
        for item in data_object:
            text_parts.append(_extract_text_recursively(item))
    elif isinstance(data_object, str):
        text_parts.append(data_object)
    # Ignorar outros tipos como números, booleanos, None

    return " ".join(filter(None, text_parts)).strip()


def _extract_main_ementa_text(content_list):
    """
    Extrai o texto da ementa principal de uma lista de conteúdos de página.
    Concatena o 'body' e os 'points' da primeira ementa encontrada.
    """
    for page_content in content_list:
        if isinstance(page_content, dict) and "ementa" in page_content:
            ementa_data = page_content["ementa"]
            if isinstance(ementa_data, dict):
                body = ementa_data.get("body", "")
                points = ementa_data.get("points", [])
                if isinstance(points, list):
                    full_ementa_text = body
                    for point in points:
                        if isinstance(point, str):
                            full_ementa_text += " " + point
                    return full_ementa_text.strip()
                return body.strip() # Caso 'points' não seja uma lista ou esteja ausente
    return "" # Retorna string vazia se nenhuma ementa for encontrada


# --- NOVA LÓGICA DE CARREGAMENTO DE DADOS ---
def load_processes_from_original_json(path_to_original_json_file):
    """
    MODIFICADO: Carrega dados do arquivo JSON ORIGINAL completo.
    Extrai todo o texto relevante de cada documento para RAG e
    o texto da ementa principal para exibição.
    """
    documents_for_rag = []
    print(f"Carregando dados do arquivo JSON ORIGINAL: {path_to_original_json_file}...")
    try:
        with open(path_to_original_json_file, 'r', encoding='utf-8') as f:
            original_data_list = json.load(f)

        if not isinstance(original_data_list, list):
            print(f"ERRO: O arquivo JSON em {path_to_original_json_file} não é uma lista na raiz.")
            return []

        for doc_original in original_data_list:
            if not isinstance(doc_original, dict) or "fileName" not in doc_original or "content" not in doc_original:
                print(f"ALERTA: Item no JSON original não tem a estrutura esperada (fileName/content): {doc_original}")
                continue

            file_name_source = doc_original.get("fileName", "FonteDesconhecida_" + str(len(documents_for_rag)))
            content_list = doc_original.get("content", [])

            # Extrai todo o texto do "content" para o RAG
            # A função _extract_text_recursively vai varrer a lista 'content'
            text_content_for_rag = _extract_text_recursively(content_list)

            # Extrai o texto da ementa principal para exibição
            ementa_text_for_display = _extract_main_ementa_text(content_list)

            # Coleta alguns metadados importantes para referência
            # Você pode expandir isso conforme necessário
            doc_metadata = {
                "fileName": file_name_source,
                "case_info": None, # Tenta encontrar o primeiro case_info
                "relator": None # Tenta encontrar o primeiro relator
            }
            for page in content_list:
                if isinstance(page, dict):
                    if not doc_metadata["case_info"] and "case_info" in page:
                        doc_metadata["case_info"] = page["case_info"]
                    if not doc_metadata["relator"] and "parties_and_roles" in page and "relator" in page["parties_and_roles"]:
                        doc_metadata["relator"] = page["parties_and_roles"]["relator"]
                    if doc_metadata["case_info"] and doc_metadata["relator"]: # Otimização
                        break
            
            if text_content_for_rag.strip():
                documents_for_rag.append({
                    "source": file_name_source,
                    "text": text_content_for_rag,         # Texto completo para chunking e embeddings
                    "ementa_display_text": ementa_text_for_display if ementa_text_for_display else "Ementa não encontrada.", # Para exibição
                    "full_metadata_origem": doc_metadata # Metadados básicos do documento
                })
            else:
                print(f"ALERTA: Documento '{file_name_source}' com texto extraído vazio.")

    except FileNotFoundError:
        print(f"ERRO: Arquivo JSON original não encontrado em '{path_to_original_json_file}'")
        return []
    except json.JSONDecodeError:
        print(f"ERRO: Falha ao decodificar o JSON original em '{path_to_original_json_file}'")
        return []
    except Exception as e:
        print(f"ERRO inesperado ao processar o JSON original '{path_to_original_json_file}': {e}")
        return []

    print(f"{len(documents_for_rag)} documentos carregados e preparados para RAG a partir do arquivo JSON original.")
    return documents_for_rag

# --- Etapa 2: Segmentação (Chunking) ---
# (Função chunk_text mantida como estava)
def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return [chunk for chunk in chunks if chunk.strip()]


# --- Etapa 3: Processamento e Geração de Embeddings ---
# (Função process_documents_for_rag mantida como estava em sua lógica principal,
#  pois ela já espera uma lista de dicionários com "source" e "text")
def process_documents_for_rag(documents_data):
    all_chunks_with_source = []
    for doc_info in documents_data:
        source_file = doc_info.get("source", "FonteDesconhecida")
        full_text = doc_info.get("text", "") # Este é o texto completo extraído

        # Adiciona os metadados da ementa e outros relevantes ao chunk
        # para que possam ser recuperados e usados no prompt ou exibição
        chunk_metadata = {
            "source_document": source_file,
            "ementa_original": doc_info.get("ementa_display_text", ""),
            "outros_metadados_doc": doc_info.get("full_metadata_origem", {})
        }

        if not full_text.strip():
            print(f"Alerta: Documento da fonte '{source_file}' não possui conteúdo textual para processar.")
            continue

        text_chunks = chunk_text(full_text)
        
        for chunk_content in text_chunks:
            if chunk_content.strip():
                all_chunks_with_source.append({
                    "source_document_chunk_specific": source_file, # Fonte específica do chunk
                    "text_chunk": chunk_content,
                    "metadata_chunk": chunk_metadata # Adiciona os metadados ao chunk
                })

    if not all_chunks_with_source:
        print("Alerta: Nenhum chunk de texto foi gerado.")
    print(f"Total de {len(all_chunks_with_source)} chunks de texto criados.")
    return all_chunks_with_source


# --- Etapa 4: Criação do Vector Store (FAISS) ---
# (Função create_vector_store ligeiramente ajustada para lidar com a nova estrutura de chunks)
def create_vector_store(chunks_with_metadata, embedding_model):
    if not chunks_with_metadata:
        print("Nenhum chunk de texto fornecido para criar o vector store.")
        return None, []

    texts_to_embed = [chunk["text_chunk"] for chunk in chunks_with_metadata if chunk.get("text_chunk", "").strip()]

    if not texts_to_embed:
        print("Nenhum texto válido encontrado nos chunks para gerar embeddings.")
        return None, []

    print(f"Gerando embeddings para {len(texts_to_embed)} chunks de texto...")
    embeddings = embedding_model.encode(texts_to_embed, show_progress_bar=True)
    print("Embeddings gerados.")

    if embeddings.ndim == 1: # Caso de apenas um texto
        embeddings = np.expand_dims(embeddings, axis=0)
    if embeddings.shape[0] == 0: # Caso nenhum embedding tenha sido gerado
        print("Nenhum embedding foi gerado. O Vector Store não pode ser criado.")
        return None, []


    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    print(f"Vector store FAISS criado com {index.ntotal} vetores.")
    # Retorna o índice e a lista original de chunks com metadados, pois ela contém mais info
    return index, chunks_with_metadata


# --- Etapa 5: Recuperação (Retrieval) ---
# (Função retrieve_relevant_chunks ajustada para usar a lista de chunks com metadados)
def retrieve_relevant_chunks(query, vector_store_index, all_chunks_with_metadata_list, embedding_model, top_k=3):
    if vector_store_index is None or vector_store_index.ntotal == 0:
        print("Vector store não inicializado ou vazio.")
        return []
    if not query:
        print("Query vazia.")
        return []

    print(f"Gerando embedding para a query: '{query}'")
    query_embedding = embedding_model.encode([query])
    if query_embedding.ndim == 1:
         query_embedding = np.expand_dims(query_embedding, axis=0)

    print(f"Buscando {top_k} chunks mais relevantes...")
    distances, indices = vector_store_index.search(query_embedding.astype('float32'), top_k)
    
    relevant_chunks_data = []
    if indices.size > 0:
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if 0 <= idx < len(all_chunks_with_metadata_list):
                # Retorna o objeto completo do chunk, que inclui o texto e os metadados
                relevant_chunks_data.append(all_chunks_with_metadata_list[idx])
            else:
                print(f"Alerta: Índice {idx} fora do intervalo da lista de chunks (tamanho: {len(all_chunks_with_metadata_list)}).")
    
    print(f"{len(relevant_chunks_data)} chunks relevantes encontrados.")
    return relevant_chunks_data


# --- Etapa 6: Geração da Resposta com LLM ---
# (Função generate_response_with_llm ajustada para usar metadados se necessário)
def generate_response_with_llm(query, relevant_chunks_data, llm_model):
    if not relevant_chunks_data:
        context_from_chunks = "Nenhuma informação específica encontrada nos documentos para esta pergunta."
        sources_info = "Nenhuma fonte específica."
    else:
        context_from_chunks = "\n\n---\n\n".join([chunk_data["text_chunk"] for chunk_data in relevant_chunks_data])
        # Você pode querer listar as fontes (fileName) ou ementas dos documentos dos chunks recuperados
        source_files_cited = list(set([chunk_data["metadata_chunk"]["source_document"] for chunk_data in relevant_chunks_data]))
        sources_info = "Fontes consultadas: " + ", ".join(source_files_cited)
        # Poderia também incluir as ementas aqui se quisesse mostrá-las no prompt ou na resposta
        # ementas_citadas = "\n".join([f"Ementa de {chunk_data['metadata_chunk']['source_document']}:\n{chunk_data['metadata_chunk']['ementa_original']}\n" for chunk_data in relevant_chunks_data])


    prompt = f"""
    Você é VeritasJuris, um assistente de IA especializado em Direito brasileiro.
    Sua tarefa é responder à pergunta do usuário de forma clara, concisa e fundamentada EXCLUSIVAMENTE
    nas informações contidas nos seguintes trechos de jurisprudência.
    Não utilize conhecimento externo. Se a informação não estiver nos trechos, diga que não pode responder com base no material fornecido.
    Ao final da sua resposta, mencione os documentos que foram consultados, se houver.

    TRECHOS DA JURISPRUDÊNCIA (use estes para basear sua resposta):
    {context_from_chunks}

    PERGUNTA DO USUÁRIO:
    {query}

    RESPOSTA FUNDAMENTADA:
    [Sua resposta aqui]

    {sources_info}
    """
    print("Gerando resposta com LLM (baseado em chunks)...")
    try:
        response = llm_model.generate_content(prompt)
        print("Resposta gerada.")
        return response.text
    except Exception as e:
        print(f"Erro ao gerar resposta com o LLM: {e}")
        return "Ocorreu um erro ao tentar gerar a resposta principal. Por favor, tente novamente."

# --- Exemplo de fluxo principal (main) ---
if __name__ == '__main__':
    # Configurações
    NOME_ARQUIVO_JSON_ORIGINAL = 'SEU_ARQUIVO_JSON_COMPLETO.json' # <--- SUBSTITUA PELO NOME DO SEU ARQUIVO JSON COMPLETO
    
    # Verifica se o arquivo JSON existe
    if not os.path.exists(NOME_ARQUIVO_JSON_ORIGINAL):
        print(f"ERRO CRÍTICO: O arquivo JSON original '{NOME_ARQUIVO_JSON_ORIGINAL}' não foi encontrado.")
        print("Por favor, coloque o arquivo JSON na mesma pasta do script ou forneça o caminho completo.")
        print("Este script espera o JSON com a estrutura original dos documentos (contendo 'fileName' e 'content' por página).")
        exit()

    embedding_model = initialize_embedding_model()
    llm_model = configure_llm()

    # 1. Carregar e Pré-processar os documentos do JSON original
    print("Iniciando carregamento e pré-processamento dos documentos...")
    documents_data_for_rag = load_processes_from_original_json(NOME_ARQUIVO_JSON_ORIGINAL)

    if not documents_data_for_rag:
        print("Nenhum documento foi carregado. Verifique o arquivo JSON e os logs.")
    else:
        # 2. Segmentar os textos dos documentos
        print("\nIniciando segmentação dos textos...")
        all_chunks_with_metadata = process_documents_for_rag(documents_data_for_rag)

        if not all_chunks_with_metadata:
            print("Nenhum chunk foi gerado. O pipeline não pode continuar sem chunks.")
        else:
            # 3. Criar o Vector Store
            print("\nIniciando criação do vector store...")
            vector_store, all_chunks_for_reference = create_vector_store(all_chunks_with_metadata, embedding_model)

            if vector_store:
                print("\n--- Pipeline RAG pronto para consultas ---")
                # Exemplo de consulta
                # query = "Qual o entendimento sobre a necessidade de notificação em execução fiscal de anuidades de conselho profissional?"
                query = "Qual o entendimento do STJ sobre apropriação indébita tributária e a necessidade de dolo específico?"
                
                # 4. Recuperar chunks relevantes
                relevant_chunks = retrieve_relevant_chunks(query, vector_store, all_chunks_for_reference, embedding_model, top_k=5)
                
                # 5. Gerar resposta com LLM
                final_response = generate_response_with_llm(query, relevant_chunks, llm_model)
                
                print("\n--- RESPOSTA FINAL ---")
                print(final_response)

                print("\n--- CHUNKS RELEVANTES USADOS ---")
                for i, chunk_data in enumerate(relevant_chunks):
                    print(f"\nChunk {i+1} (Fonte: {chunk_data['metadata_chunk']['source_document']}):")
                    print(f"Ementa Original (se disponível): {chunk_data['metadata_chunk']['ementa_original']}")
                    print(f"Texto do Chunk: {chunk_data['text_chunk'][:300]}...") # Mostra os primeiros 300 caracteres
                    print("---")
            else:
                print("Falha ao criar o vector store. Pipeline não pode prosseguir.")