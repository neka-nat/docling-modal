import modal

image = (
    modal.Image.from_registry("nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04", add_python="3.12")
    .pip_install("fastapi[standard]==0.115.4")
    .pip_install("docling>=2.5.2")
    .pip_install("pypdf")
)

app = modal.App("docling-app", image=image)


@app.cls(
    gpu="t4",
    timeout=600,
    mounts=[modal.Mount.from_local_file("./test.pdf", remote_path="/root/test.pdf")],
)
class Model:
    @modal.build()
    def download_model(self):
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        converter.convert("/root/test.pdf")

    @modal.enter()
    def initialize_model(self):
        from docling.document_converter import DocumentConverter
        self.converter = DocumentConverter()

    @modal.method()
    def convert_pdf_to_md(self, pdf_data: bytes) -> str:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            temp_file.write(pdf_data)
            temp_file_path = temp_file.name
            return self.converter.convert(temp_file_path).document.export_to_markdown()

    @modal.method()
    def convert_pdf_pages_to_md(self, pdf_data_list: list[bytes]) -> list[str]:
        import io
        from docling.datamodel.base_models import DocumentStream
        sources: list[DocumentStream] = []
        for i, pdf_data in enumerate(pdf_data_list):
            stream = io.BytesIO()
            stream.write(pdf_data)
            stream.seek(0)
            sources.append(DocumentStream(name=f"page-{i}.pdf", stream=stream))
        results = self.converter.convert_all(sources, raises_on_error=False)
        return [res.document.export_to_markdown() for res in results]



@app.function(image=image)
@modal.asgi_app()
def web():
    import json
    import io
    from fastapi import FastAPI, File, UploadFile, Response
    from pypdf import PdfReader, PdfWriter

    app = FastAPI()

    @app.post("/convert")
    async def convert(file: UploadFile = File(...)) -> dict:
        model = Model()
        pdf_data_list: list[bytes] = []
        with io.BytesIO() as temp_file:
            temp_file.write(await file.read())
            temp_file.seek(0)
            reader = PdfReader(temp_file)
            for page in reader.pages:
                output_stream = io.BytesIO()
                writer = PdfWriter()
                writer.add_page(page)
                writer.write(output_stream)
                output_stream.seek(0)
                pdf_data_list.append(output_stream.getvalue())
        return Response(json.dumps(await model.convert_pdf_pages_to_md.remote.aio(pdf_data_list)))

    return app


@app.local_entrypoint()
def main(input_test_pdf: str = "./test.pdf"):
    modal = Model()
    with open(input_test_pdf, "rb") as f:
        pdf_data = f.read()
    print(modal.convert_pdf_to_md.remote(pdf_data))
