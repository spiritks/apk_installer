import streamlit as st
import subprocess
from adbutils import adb
import os
import requests
import pandas as pd
import rethinkdb as r
from rethinkdb import RethinkDB
import time
from dotenv import load_dotenv
load_dotenv()


def del_device(serial=None):
    if serial!=None:
        r = RethinkDB()
        conn = r.connect(host='localhost', port=28015)
        db = r.db('stf')
        table = db.table('devices')
        result = table.filter(r.row['serial'] == serial).delete().run(conn)
        return result
    return None
def send_api_request(url, method='GET', params=None, data=None, headers=None):
    """
    Отправляет API-запрос и возвращает ответ.

    :param url: URL API.
    :param method: Метод HTTP-запроса (GET, POST, PUT, DELETE и т.д.).
    :param params: Параметры запроса для методов GET и DELETE.
    :param data: Данные для отправки (например, в формате JSON) для методов POST и PUT.
    :param headers: Заголовки HTTP-запроса.
    :return: Ответ сервера (response object).
    """
    if headers==None:
        token = os.getenv("STF_API_TOKEN")
        if token:
            headers = {"Authorization": f"Bearer {token}"}
        else:
            headers = None
    url =  f"{os.getenv('URL_API_BASE')}/api/v1/"+str(url)
    print(url)
    print(headers)
    try:
        response = requests.request(method=method, url=url, params=params, json=data, headers=headers)

        # Проверяем, успешен ли запрос
        response.raise_for_status()
        
        # Возвращаем ответ в формате JSON, если это возможно
        try:
            return response.json()
        except ValueError:
            return response.text
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")


def GetDevicesFromSTF(Devices_Serials=None):
    
    resp = send_api_request('devices')
    if Devices_Serials==None:
        if not isinstance(resp,str):
            devices_list = []
            devices = resp["devices"]
            
            for device in devices:
                try:
                    devices_list.append({"Notes":device["notes"],"Serial":device["serial"]})
                except:
                    pass
            return pd.DataFrame(devices_list)
    else:
        return None
    return resp

def install_apk(device_id, apk_path):
    try:
        # Устанавливаем APK на устройство
        subprocess.run(["adb", "-s", device_id, "install", apk_path], check=True)
        
        # Копируем APK в папку Downloads/Autoinstalled_APKs
        remote_path = "/sdcard/Download/Autoinstalled_APKs/"
        subprocess.run(["adb", "-s", device_id, "shell", "mkdir", "-p", remote_path], check=True)
        subprocess.run(["adb", "-s", device_id, "push", apk_path, remote_path], check=True)
        
        st.success(f"APK установлено и скопировано в {remote_path} на устройство {device_id}")
    except subprocess.CalledProcessError as e:
        st.error(f"Ошибка при установке APK на устройство {device_id}: {e}")

def restart_service(device_id, service_name):
    try:
        subprocess.run(["adb", "-s", device_id, "shell", "am", "stopservice", service_name], check=True)
        subprocess.run(["adb", "-s", device_id, "shell", "am", "startservice", service_name], check=True)
        st.success(f"Служба {service_name} перезапущена на устройстве {device_id}")
    except subprocess.CalledProcessError as e:
        st.error(f"Ошибка при перезапуске службы {service_name} на устройстве {device_id}: {e}")
def get_adb_devices():
    # Выполнение команды adb devices
    result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Получение вывода команды
    output = result.stdout.decode('utf-8')
    
    # Обработка вывода, чтобы получить список устройств и их статус
    devices = []
    for line in output.splitlines():
        if "\t" in line:  # строки с устройствами содержат символ табуляции между серийным номером и статусом
            device_info = line.split("\t")
            devices.append({"Serial": device_info[0], "Status": device_info[1]})
    try:    
        return pd.DataFrame(devices)
    except:
        return None
def get_connected_devices():
    try:
        devices = adb.device_list()
        return [{"Serial":device.serial} for device in devices]
    except Exception as e:
        st.error(f"Ошибка при получении списка подключенных устройств: {e}")
        return []

def reboot():
    
    try:
        result = subprocess.run('ssh root@127.0.0.1 sudo reboot', shell=True, check=True)
        st.write(result)
    except subprocess.CalledProcessError as e:
        st.title("System is rebooting now")

    
    
def main():
    # st.write(os.getenv("STF_API_TOKEN"))
    # st.write(os.getenv("URL_API_BASE"))
    global stfDevlist
    st.title("APK Installer and Service Restarter")
    if st.button("Rebot"):
            reboot()
    stfDevlist = GetDevicesFromSTF()
    st.header("Список устройств")
    adb_devices = get_adb_devices()
    adb_devices=(pd.merge(adb_devices,GetDevicesFromSTF(),on='Serial'))
    st.write(adb_devices)
    st.write(f"Total devices connected to ADB is {len(adb_devices)}")
    devices_serials = pd.DataFrame(get_connected_devices())
    
    st.header("Шаг 1: Загрузите APK")
    apk_file = st.file_uploader("Выберите APK файл", type=["apk"])

    st.header("Шаг 2: Выберите подключенные устройства")
    
    
    devicelist=pd.merge(devices_serials,stfDevlist,on="Serial")
    
    device_to_delete = GetDevicesFromSTF()
    device_to_delete = device_to_delete[device_to_delete["Notes"]=="Удалить"]
    if len(device_to_delete)>0:
        st.write(device_to_delete)
        if st.button("Удалить Помеченные устройства"):
            for dev in device_to_delete['Serial'].to_list():
                st.write(del_device(dev))
    selected_devices = st.multiselect("Устройства", devicelist["Notes"])

    # st.header("Шаг 3: Укажите службу для перезапуска")
    # service_name = st.text_input("Имя службы",value="com.sms.messages.service.MainService")

    if apk_file is not None and selected_devices:
        apk_temp_path = f"/tmp/{apk_file.name}"
        with open(apk_temp_path, "wb") as f:
            f.write(apk_file.getbuffer())
        
        if st.button("Установить APK и перезапустить службу"):
            for device_id in selected_devices:
                # st.write(devicelist[devicelist["Notes"]==device_id])
                device_id = devicelist[devicelist["Notes"]==device_id].iloc[0]['Serial']
                # st.write(device_id)
                install_apk(device_id, apk_temp_path)
                # restart_service(device_id, service_name)
                
        # Удаляем временный файл после использования
        if os.path.exists(apk_temp_path):
            os.remove(apk_temp_path)
    if selected_devices:
        if st.button("Restart device usb"):
            for device_id in selected_devices:
                device_id = devicelist[devicelist["Notes"]==device_id].iloc[0]['Serial']
                try:
                    subprocess.run(["adb", "-s", device_id, "usb"], check=True)
                    time.sleep(3)
                    subprocess.run(["adb", "-s", device_id, "reconnect"], check=True)
                    st.success(f"USB перезапущен на устройстве {device_id}")
                except subprocess.CalledProcessError as e:
                    st.error(f"Ошибка при перезапуске USB на устройстве {device_id}: {e}")
            
if __name__ == "__main__":
    
    main()
