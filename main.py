import io
import asyncio
import img2pdf
import uuid
import zipfile

from pdf2image import convert_from_bytes

from fastapi import FastAPI, File, UploadFile
from starlette.responses import Response

tasks = {}

app = FastAPI()

async def convert_jpg_to_pdf(jpg_file):
    try:
        loop = asyncio.get_running_loop()
        with io.BytesIO() as pdf_bytes:
            jpg_bytes = await jpg_file.read()
            pdf_data = await loop.run_in_executor(None, img2pdf.convert, jpg_bytes)
            pdf_bytes.write(pdf_data)
            pdf_bytes.seek(0)
            return pdf_bytes.read()
    
    except Exception as e:
        raise e
    
async def convert_pdf_to_jpg(pdf_bytes):
    try:
        images = await asyncio.to_thread(convert_from_bytes, pdf_bytes)
        output_bytes = io.BytesIO()
        with zipfile.ZipFile(output_bytes, 'w') as zip_file:
            for index, image in enumerate(images):
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='jpeg')
                image_bytes.seek(0)
                zip_file.writestr(f'image{index+1}.jpeg', image_bytes.getvalue())
        output_bytes.seek(0)
        return output_bytes
    
    except Exception as e:
        raise e

async def delete_completed_task(task_id):
    await asyncio.sleep(10)
    del tasks[task_id]

@app.post("/convert-to-pdf")
async def convert_to_pdf(jpg_file: UploadFile = File(...)):
    file_name = jpg_file.filename
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"file_name": file_name[:-4], "status": "waiting"}
    
    try:
        task = asyncio.create_task(convert_jpg_to_pdf(jpg_file))
        tasks[task_id]["status"] = "processing"

        pdf_bytes = await task

        tasks[task_id]["status"] = "completed"

        asyncio.create_task(delete_completed_task(task_id))
        return Response(content=pdf_bytes, media_type="application/pdf")
    
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error_message"] = str(e)
        asyncio.create_task(delete_completed_task(task_id))
        return Response(content=str(e), status_code=500)

@app.post("/convert-to-jpg")
async def convert_to_jpg(pdf_file: UploadFile = File(...)):
    
    try:
        file_name = pdf_file.filename
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"file_name": file_name[:-4], "status": "waiting"}

        pdf_bytes = await pdf_file.read()

        task = asyncio.create_task(convert_pdf_to_jpg(pdf_bytes))
        tasks[task_id]["status"] = "processing"

        output_bytes = await task

        tasks[task_id]["status"] = "completed"

        asyncio.create_task(delete_completed_task(task_id))
        return Response(content=output_bytes.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="images.zip"'})
    
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error_message"] = str(e)
        asyncio.create_task(delete_completed_task(task_id))
        return Response(content=str(e), status_code=500)

@app.get("/tasks")
async def get_tasks():
    return {"tasks": list(tasks.values())}