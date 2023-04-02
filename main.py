import io
import asyncio
import img2pdf
import uuid

from pdf2image import convert_from_bytes

from fastapi import FastAPI, File, UploadFile
from starlette.responses import Response, StreamingResponse

tasks = {}

app = FastAPI()

async def convert_jpg_to_pdf(jpg_file):
    loop = asyncio.get_running_loop()
    with io.BytesIO() as pdf_bytes:
        jpg_bytes = await jpg_file.read()
        pdf_data = await loop.run_in_executor(None, img2pdf.convert, jpg_bytes)
        pdf_bytes.write(pdf_data)
        pdf_bytes.seek(0)
        return pdf_bytes.read()
    
async def convert_pdf_to_images(pdf_bytes):
    images = await asyncio.to_thread(convert_from_bytes, pdf_bytes)
    output_bytes = io.BytesIO()
    for image in images:
        image.save(output_bytes, format='jpeg')
    output_bytes.seek(0)
    return output_bytes

async def delete_completed_task(task_id):
    await asyncio.sleep(10)
    del tasks[task_id]

@app.post("/convert-to-pdf")
async def convert_to_pdf(jpg_file: UploadFile = File(...)):
    file_name = jpg_file.filename
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"file_name": file_name[:-4], "status": "waiting"}

    task = asyncio.create_task(convert_jpg_to_pdf(jpg_file))
    tasks[task_id]["status"] = "started"

    pdf_bytes = await task

    tasks[task_id]["status"] = "completed"

    asyncio.create_task(delete_completed_task(task_id))
    return Response(content=pdf_bytes, media_type="application/pdf")

@app.post("/convert-to-jpg")
async def pdf_to_images(pdf_file: UploadFile = File(...)):
    pdf_bytes = await pdf_file.read()
    output_bytes = await convert_pdf_to_images(pdf_bytes)
    return Response(content=output_bytes.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="images.zip"'})

@app.get("/tasks")
async def get_tasks():
    return {"tasks": list(tasks.values())}
