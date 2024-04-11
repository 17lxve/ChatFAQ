import os
from logging import getLogger
from typing import List, Optional

import ray
from ray.util.scheduling_strategies import NodeAffinitySchedulingStrategy


logger = getLogger(__name__)


@ray.remote(num_cpus=1, resources={"tasks": 1})
def generate_embeddings(data):

    from chat_rag.inf_retrieval.embedding_models import E5Model

    embedding_model = E5Model(
        model_name=data["model_name"],
        use_cpu=data["device"] == "cpu",
        huggingface_key=os.environ.get("HUGGINGFACE_API_KEY", None),
    )

    embeddings = embedding_model.build_embeddings(
        contents=data["contents"], batch_size=data["batch_size"]
    )

    # from tensor to list
    embeddings = [embedding.tolist() for embedding in embeddings]

    return embeddings


@ray.remote(num_cpus=1, resources={"tasks": 1})
def parse_pdf(pdf_file, strategy, splitter, chunk_size, chunk_overlap):
    from io import BytesIO

    from chat_rag.data.parsers import parse_pdf
    from chat_rag.data.splitters import get_splitter

    pdf_file = BytesIO(pdf_file)

    splitter = get_splitter(splitter, chunk_size, chunk_overlap)

    logger.info(f"Splitter: {splitter}")
    logger.info(f"Strategy: {strategy}")
    logger.info(f"Chunk size: {chunk_size}")
    logger.info(f"Chunk overlap: {chunk_overlap}")

    parsed_items = parse_pdf(file=pdf_file, strategy=strategy, split_function=splitter)

    return parsed_items


@ray.remote(num_cpus=1, resources={"tasks": 1})
def generate_titles(contents, n_titles, lang):
    from chat_rag.inf_retrieval.query_generator import QueryGenerator

    api_key = os.environ.get("OPENAI_API_KEY", None)
    query_generator = QueryGenerator(api_key, lang=lang)

    new_titles = []
    for content in contents:
        titles = query_generator(content, n_queries=n_titles)
        new_titles.append(titles)

    return new_titles


@ray.remote(num_cpus=0.001)
def get_filesystem(storages_mode):
    """
    For Digital Ocean, we need to provide a custom filesystem object to write the index to the cloud storage
    """
    from pyarrow import fs
    from ray.data.datasource import _S3FileSystemWrapper

    if storages_mode == "do":
        
        endpoint_url = f'https://{os.environ.get("DO_REGION")}.digitaloceanspaces.com'
        s3fs = fs.S3FileSystem(
            access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            endpoint_override=endpoint_url,
        )

        # This is a hack to make the S3FileSystem object serializable (https://github.com/ray-project/ray/pull/17103)
        s3fs = _S3FileSystemWrapper(s3fs)

        print("Using Digital Ocean S3 filesystem")

        return s3fs

    # If None ray data autoinfers the filesystem
    return None


@ray.remote(num_cpus=1, resources={"tasks": 1})
class ColBERTActor:
    def __init__(self, index_path: str, device: str = 'cpu', colbert_name: Optional[str] = None, storages_mode: str = None):

        import os
        
        self.index_path = index_path
        self.colbert_name = colbert_name
        self.device = device
        self.n_gpus = -1 if self.device == "cpu" else self.get_num_gpus()
        self.storages_mode = storages_mode

        self.index_root, self.index_name = os.path.split(index_path)

        if colbert_name is not None:
            self.load_pretrained()
        else:
            self.load_index()

    def load_pretrained(self):
        """
        Load a pretrained ColBERT model without an index.
        """
        from ragatouille import RAGPretrainedModel

        self.retriever = RAGPretrainedModel.from_pretrained(
            self.colbert_name, index_root=self.index_root, n_gpu=self.n_gpus
        )
    
    def load_index(self):
        """
        Load a ColBERT model from an existing index.
        """
        from ragatouille import RAGPretrainedModel

        if 's3://' in self.index_path:    
            node_id = ray.get_runtime_context().get_node_id()
            print(f"Node ID: {node_id}")
            node_scheduling_strategy = NodeAffinitySchedulingStrategy(
                node_id=node_id, soft=False
            )
            local_index_path_ref = read_s3_index.options(scheduling_strategy=node_scheduling_strategy).remote(self.index_path, self.storages_mode)
            self.local_index_path = ray.get(local_index_path_ref)
        else:
            self.local_index_path = self.index_path

        self.retriever = RAGPretrainedModel.from_index(self.local_index_path, n_gpu=self.n_gpus)

    def get_num_gpus(self):
        try:
            import torch

            return torch.cuda.device_count()
        except:
            return -1
        
    def index(self, contents, contents_pk, bsize=32):
        """
        Index a collection of documents.
        """
        self.local_index_path = self.retriever.index(
            index_name=self.index_name,
            collection=contents,
            document_ids=contents_pk,
            split_documents=True,
            max_document_length=512,
            bsize=bsize,
        )
    
    def delete_from_index(self, k_item_ids_to_remove):
        """
        Delete items from the index.
        """

        print("Deleting items from the index")
        self.retriever.delete_from_index(
            document_ids=k_item_ids_to_remove,
            index_name=self.index_name,
        )
        print("Done!")

    def add_to_index(self, contents_to_add, contents_pk_to_add, bsize=32):
        """
        Add new items to the index.
        """
        print("Adding new items to the index")
        self.retriever.add_to_index(
            new_collection=contents_to_add,
            new_document_ids=contents_pk_to_add,
            index_name=self.index_name,
            split_documents=True,
            bsize=bsize,
        )
        print("Done!")

    def save_index(self):
        """
        Save the index to the cloud storage.
        """

        from ray.data.datasource import FilenameProvider

        class PidDocIdFilenameProvider(FilenameProvider):
            """
            Custom filename provider for the index to keep the original filenames, instead of the ray.data generated filenames.
            """
            def get_filename_for_row(self, row, task_index, block_index, row_index):
                path = row['path']

                filename = os.path.basename(path)
                filename = os.path.splitext(filename)[0] + f"_{self._dataset_uuid}_"
                file_id = f"{task_index:06}_{block_index:06}_{row_index:06}.parquet"
                filename += file_id

                return filename
            
            def get_filename_for_block(self, block, task_index: int, block_index: int) -> str:

                path = str(block['path'][0])

                filename = os.path.basename(path)
                filename = os.path.splitext(filename)[0] + "_"
                file_id = f"{task_index:06}_{block_index:06}.parquet"
                filename += file_id
                
                return filename

        try:
            print("Saving index...")

            if "s3://" in self.index_path:
                fs_ref = get_filesystem.remote(self.storages_mode)

                print('Reading index from local storage')
                # Update the index path to use the unique index path
                ray_local_index_path = 'local://' + os.path.join(os.getcwd(), self.retriever.model.index_path)
                index = ray.data.read_binary_files(ray_local_index_path, include_paths=True)

                print(f"Writing index to object storage {self.index_path}")
                print(f'Size of index: {index.size_bytes()/1e9:.2f} GB')

                fs = ray.get(fs_ref)
                if fs is not None:
                    # unwrap the filesystem object
                    fs = fs.unwrap()
                # Then we can write the index to the cloud storage
                index.write_parquet(self.index_path, filesystem=fs, filename_provider=PidDocIdFilenameProvider())
                print('Index written to object storage')

            return True
        
        except Exception as e:
            print(f"Error saving index: {e}")
            return False
        
    def exit(self):
        ray.actor.exit_actor()


@ray.remote(num_cpus=1, resources={"tasks": 1})
def create_colbert_index(
    colbert_name, bsize, device, s3_index_path, storages_mode, contents_pk, contents
):
    
    from typing import Dict

    from ray.data.datasource import FilenameProvider


    class PidDocIdFilenameProvider(FilenameProvider):

        def get_filename_for_row(self, row, task_index, block_index, row_index):
            path = row['path']

            filename = os.path.basename(path)
            filename = os.path.splitext(filename)[0] + f"_{self._dataset_uuid}_"
            file_id = f"{task_index:06}_{block_index:06}_{row_index:06}.parquet"
            filename += file_id

            return filename
        
        def get_filename_for_block(self, block: Dict, task_index: int, block_index: int) -> str:

            path = str(block['path'][0])

            filename = os.path.basename(path)
            filename = os.path.splitext(filename)[0] + "_"
            file_id = f"{task_index:06}_{block_index:06}.parquet"
            filename += file_id
            
            return filename

    def get_num_gpus():
        try:
            import torch

            return torch.cuda.device_count()
        except:
            return -1

    try:

        from ragatouille import RAGPretrainedModel


        index_root, index_name = os.path.split(s3_index_path)
        print(f'S3 index path: {s3_index_path}')
        print(f"Index root: {index_root}, Index name: {index_name}")

        if "s3://" in index_root:
            # get the index root folder, we don't care about the bucket right now
            _, index_root = os.path.split(index_root)

        n_gpus = -1 if device == "cpu" else get_num_gpus()

        retriever = RAGPretrainedModel.from_pretrained(
            colbert_name, index_root=index_root, n_gpu=n_gpus
        )

        # Update the index path to use the unique index path
        local_index_path = retriever.index(
            index_name=index_name,
            collection=contents,
            document_ids=contents_pk,
            split_documents=True,
            max_document_length=512,
            bsize=bsize,
        )

        print(f"Local index path: {local_index_path}")

        # if cloud storage, then we write the index to the cloud storage
        if "s3://" in s3_index_path:
            # We read the index as binary files into a table with the schema, where each file is a row:
            # Column  Type
            # ------  ----
            # bytes   binary
            # path    string,
            fs_ref = get_filesystem.remote(storages_mode)

            print('Reading index from local storage')
            local_index_path = 'local://' + os.path.join(os.getcwd(), local_index_path)
            index = ray.data.read_binary_files(local_index_path, include_paths=True)

            print(f"Writing index to object storage {s3_index_path}")
            print(f'Size of index: {index.size_bytes()/1e9:.2f} GB')

            fs = ray.get(fs_ref)
            if fs is not None:
                # unwrap the filesystem object
                fs = fs.unwrap()
            
            # Then we can write the index to the cloud storage
            index.write_parquet(s3_index_path, filesystem=fs, filename_provider=PidDocIdFilenameProvider())
            print('Index written to object storage')

            index_f = index.filter(lambda x: x["path"].endswith('pid_docid_map.json'))

            # remove path column
            index_f = index_f.drop_columns(["path"])

        # success
        return True

    except Exception as e:
        print(f"Error creating index: {e}")
        # failure
        return False


@ray.remote(num_cpus=1, resources={"tasks": 1})
def modify_colbert_index(index_path: str, k_item_ids_to_remove: List[str], contents_to_add: List[str], contents_pk_to_add: List[str], storages_mode: str, bsize: int):

    from ragatouille import RAGPretrainedModel

    # Schedule the reading of the index on the same node as the deployment
    node_id = ray.get_runtime_context().get_node_id()
    print(f"Node ID: {node_id}")
    node_scheduling_strategy = NodeAffinitySchedulingStrategy(
            node_id=node_id, soft=False
    )

    if 's3://' in index_path:
        index_path_ref = read_s3_index.options(scheduling_strategy=node_scheduling_strategy).remote(index_path, storages_mode)
        index_path = ray.get(index_path_ref)
        index_name = os.path.basename(index_path)
    else:
        index_root, index_name = os.path.split(index_path)
        index_path = os.path.join(index_root, 'colbert', 'indexes', index_name)
        print(f'Reading index locally from {index_path}')

    print(f"Loading index from {index_path}")
    retriever = RAGPretrainedModel.from_index(index_path)

    print("Deleting items from the index")
    # remove the items from the index
    retriever.delete_from_index(
            document_ids=k_item_ids_to_remove,
            index_name=index_name,
    )
    
    print("Adding new items to the index")

    retriever.add_to_index(
            new_collection=contents_to_add,
            new_document_ids=contents_pk_to_add,
            index_name=index_name,
            split_documents=True,
            max_document_length=512,
            bsize=bsize,
        )
    
    print("Done!")
    
    return False


@ray.remote(num_cpus=1)
def read_s3_index(index_path, storages_mode):
    """
    If the index_path is an S3 path, read the index from object storage and write it to the local storage.
    """
    fs_ref = get_filesystem.remote(storages_mode)

    from tqdm import tqdm

    def write_file(row, base_path):
        # Extract bytes and path from the row
        content, file_path = row["bytes"], row["path"]

        file_name = os.path.basename(file_path)

        # Combine the base path with the original file path
        full_path = os.path.join(base_path, file_name)

        print(f"Writing file to {full_path}")

        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write the file
        with open(full_path, "wb") as file:
            file.write(content)

    print(f"Reading index from {index_path}")

    from pyarrow.fs import FileSelector

    fs = ray.get(fs_ref)

    if fs is not None:
        # unwrap the filesystem object
        fs = fs.unwrap()

    files = fs.get_file_info(FileSelector(index_path.split('s3://')[1]))

    file_paths = [file.path for file in files]

    # print total index size in MB
    print(f"Downloading index with size: {sum(file.size for file in files) / 1e9:.3f} GB")

    # TODO: Maybe pass the Memory resource requirement with the index size so if you have not enough memory it will not download the index
    # If the index is too large, issue an error asking the user to increase the memory resources
    index = ray.data.read_parquet_bulk(file_paths, filesystem=fs)
    print(f"Downloaded {index.count()} files from S3")

    index_name = os.path.basename(index_path)
    index_path = os.path.join("back", "indexes", "colbert", "indexes", index_name)

    # if the directory exists, delete it
    if os.path.exists(index_path):
        print(f"Deleting existing index at {index_path}")
        import shutil
        shutil.rmtree(index_path)

    print(f"Writing index to {index_path}")
    for row in tqdm(index.iter_rows()):
        write_file(row, index_path)
    return index_path



@ray.remote(num_cpus=1, resources={"tasks": 1})
def test_task(argument_one):
    import time
    print("with arg: ", argument_one, "start")
    time.sleep(5)
    print("with arg: ", argument_one, "finished")

    return 123456789