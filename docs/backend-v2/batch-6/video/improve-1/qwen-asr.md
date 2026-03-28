千问系列的录音文件识别模型能将录制好的音频转换为文本，支持多语言识别、歌唱识别、噪声拒识等功能。

## **核心功能**

-   **多语种识别：**支持多语种语音识别（涵盖普通话及多种方言，如粤语、四川话等）。
    
-   **复杂环境适应：**具备应对复杂声学环境的能力，支持自动语种检测与智能非人声过滤。
    
-   **歌唱识别：**即使在伴随背景音乐（BGM）的情况下，也能实现整首歌曲的转写。
    
-   **情感识别：**支持多种情绪状态识别（涵盖惊讶、平静、愉快、悲伤、厌恶、愤怒和恐惧）。
    

## **适用范围**

**支持的模型：**

服务主要提供两大核心模型：

-   **千问3-ASR-Flash-Filetrans**：专为长音频（最长12小时）的异步识别设计，适用于会议记录、访谈整理等场景。
    
-   **千问3-ASR-Flash**：专为短音频（最长5分钟）的同步或流式识别设计，适用于语音消息、实时字幕等场景。
    

## 中国内地

在[中国内地部署模式](https://help.aliyun.com/zh/model-studio/regions/#080da663a75xh)下，接入点与数据存储均位于**北京地域**，模型推理计算资源仅限于中国内地。

调用以下模型时，请选择北京地域的[API Key](https://bailian.console.aliyun.com/?tab=model#/api-key)：

-   **千问3-ASR-Flash-Filetrans：**qwen3-asr-flash-filetrans（稳定版，当前等同qwen3-asr-flash-filetrans-2025-11-17）、qwen3-asr-flash-filetrans-2025-11-17（快照版）
    
-   **千问3-ASR-Flash：**qwen3-asr-flash（稳定版，当前等同qwen3-asr-flash-2025-09-08）、qwen3-asr-flash-2026-02-10（最新快照版）、qwen3-asr-flash-2025-09-08（快照版）
    
-   **千问Audio ASR：**qwen-audio-asr（稳定版）
    
    千问Audio ASR为Beta版，目前仅供免费体验，免费额度用完后不支持调用，推荐使用千问3-ASR-Flash-Filetrans或千问3-ASR-Flash
    

## 国际

在[国际部署模式](https://help.aliyun.com/zh/model-studio/regions/#080da663a75xh)下，接入点与数据存储均位于**新加坡地域**，模型推理计算资源在全球范围内动态调度（不含中国内地）。

调用以下模型时，请选择新加坡地域的[API Key](https://modelstudio.console.aliyun.com/?tab=dashboard#/api-key)：

-   **千问3-ASR-Flash-Filetrans：**qwen3-asr-flash-filetrans（稳定版，当前等同qwen3-asr-flash-filetrans-2025-11-17）、qwen3-asr-flash-filetrans-2025-11-17（快照版）
    
-   **千问3-ASR-Flash：**qwen3-asr-flash（稳定版，当前等同qwen3-asr-flash-2025-09-08）、qwen3-asr-flash-2026-02-10（最新快照版）、qwen3-asr-flash-2025-09-08（快照版）
    

## 美国

在[美国部署模式](https://help.aliyun.com/zh/model-studio/regions/#080da663a75xh)下，接入点与数据存储均位于**美国（弗吉尼亚）地域**，模型推理计算资源仅限于美国境内。

调用以下模型时，请选择美国地域的[API Key](https://modelstudio.console.aliyun.com/us-east-1?tab=dashboard#/api-key)：

**千问3-ASR-Flash：**qwen3-asr-flash-us（稳定版，当前等同qwen3-asr-flash-2025-09-08-us）、qwen3-asr-flash-2025-09-08-us（快照版）

更多信息请参见[模型列表](https://help.aliyun.com/zh/model-studio/models)

## **模型选型**

| **场景** | **推荐模型** | **理由** | **注意事项** |
| --- | --- | --- | --- |
| **长音频识别** | qwen3-asr-flash-filetrans | 支持最长12小时录音，具备情感识别与句/字级别时间戳功能，适合后期索引与分析 | 音频文件大小不超过2GB，且时长不超过12小时 |
| **短音频识别** | qwen3-asr-flash或qwen3-asr-flash-us | 短音频识别，低延迟 | 音频文件大小不超过10MB，且时长不超过5分钟 |
| **客服质检** | qwen3-asr-flash-filetrans、qwen3-asr-flash或qwen3-asr-flash-us | 可分析客户情绪 | 不支持敏感词过滤；无说话人分离；根据音频时长选择合适的模型 |
| **新闻/访谈节目字幕生成** | qwen3-asr-flash-filetrans | 长音频+标点预测+时间戳，直接生成结构化字幕 | 需后处理生成标准字幕文件；根据音频时长选择合适的模型 |
| **多语种视频本地化** | qwen3-asr-flash-filetrans、qwen3-asr-flash或qwen3-asr-flash-us | 覆盖多种语言+方言，适合跨语种字幕制作 | 根据音频时长选择合适的模型 |
| **歌唱类音频分析** | qwen3-asr-flash-filetrans、qwen3-asr-flash或qwen3-asr-flash-us | 识别歌词并分析情绪，适用于歌曲索引与推荐 | 根据音频时长选择合适的模型 |

更多说明请参见[模型功能特性对比](#ea5edc7ae4cq7)。

## **快速开始**

API 使用前提：已[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)。如果通过SDK调用，需要[安装最新版SDK](https://help.aliyun.com/zh/model-studio/install-sdk#8833b9274f4v8)。

## DashScope

## 千问3-ASR-Flash-Filetrans

千问3-ASR-Flash-Filetrans模型专为音频文件的异步转写设计，支持最长12小时录音。该模型要求输入为公网可访问的音频文件URL，不支持直接上传本地文件。此外，它是一个非流式接口，会在任务完成后一次性返回全部识别结果。

## cURL

使用 cURL 进行语音识别时，需先提交任务获取任务ID（task\_id），再通过该ID获取任务执行结果。

## 提交任务

```
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/asr/transcription
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-H "X-DashScope-Async: enable" \
-d '{
    "model": "qwen3-asr-flash-filetrans",
    "input": {
        "file_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
    },
    "parameters": {
        "channel_id":[
            0
        ],
        "enable_itn": false,
        "enable_words": true
    }
}'
```

## 获取任务执行结果

```
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}，注意，将{task_id}替换为待查询任务ID
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X GET 'https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "X-DashScope-Async: enable" \
-H "Content-Type: application/json"
```

## 完整示例

## Java

```
import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import okhttp3.*;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

public class Main {
    // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/asr/transcription
    private static final String API_URL_SUBMIT = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription";
    // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/tasks/
    private static final String API_URL_QUERY = "https://dashscope.aliyuncs.com/api/v1/tasks/";
    private static final Gson gson = new Gson();

    public static void main(String[] args) {
        // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
        // 若没有配置环境变量，请用百炼API Key将下行替换为：String apiKey = "sk-xxx"
        String apiKey = System.getenv("DASHSCOPE_API_KEY");

        OkHttpClient client = new OkHttpClient();

        // 1. 提交任务
        /*String payloadJson = """
                {
                    "model": "qwen3-asr-flash-filetrans",
                    "input": {
                        "file_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                    },
                    "parameters": {
                        "channel_id": [0],
                        "enable_itn": false,
                        "language": "zh"
                    }
                }
                """;*/
        String payloadJson = """
                {
                    "model": "qwen3-asr-flash-filetrans",
                    "input": {
                        "file_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                    },
                    "parameters": {
                        "channel_id": [0],
                        "enable_itn": false,
                        "enable_words": true
                    }
                }
                """;

        RequestBody body = RequestBody.create(payloadJson, MediaType.get("application/json; charset=utf-8"));
        Request submitRequest = new Request.Builder()
                .url(API_URL_SUBMIT)
                .addHeader("Authorization", "Bearer " + apiKey)
                .addHeader("Content-Type", "application/json")
                .addHeader("X-DashScope-Async", "enable")
                .post(body)
                .build();

        String taskId = null;

        try (Response response = client.newCall(submitRequest).execute()) {
            if (response.isSuccessful() && response.body() != null) {
                String respBody = response.body().string();
                ApiResponse apiResp = gson.fromJson(respBody, ApiResponse.class);
                if (apiResp.output != null) {
                    taskId = apiResp.output.taskId;
                    System.out.println("任务已提交，task_id: " + taskId);
                } else {
                    System.out.println("提交返回内容: " + respBody);
                    return;
                }
            } else {
                System.out.println("任务提交失败! HTTP code: " + response.code());
                if (response.body() != null) {
                    System.out.println(response.body().string());
                }
                return;
            }
        } catch (IOException e) {
            e.printStackTrace();
            return;
        }

        // 2. 轮询任务状态
        boolean finished = false;
        while (!finished) {
            try {
                TimeUnit.SECONDS.sleep(2);  // 等待 2 秒再查询
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }

            String queryUrl = API_URL_QUERY + taskId;
            Request queryRequest = new Request.Builder()
                    .url(queryUrl)
                    .addHeader("Authorization", "Bearer " + apiKey)
                    .addHeader("X-DashScope-Async", "enable")
                    .addHeader("Content-Type", "application/json")
                    .get()
                    .build();

            try (Response response = client.newCall(queryRequest).execute()) {
                if (response.body() != null) {
                    String queryResponse = response.body().string();
                    ApiResponse apiResp = gson.fromJson(queryResponse, ApiResponse.class);

                    if (apiResp.output != null && apiResp.output.taskStatus != null) {
                        String status = apiResp.output.taskStatus;
                        System.out.println("当前任务状态: " + status);
                        if ("SUCCEEDED".equalsIgnoreCase(status)
                                || "FAILED".equalsIgnoreCase(status)
                                || "UNKNOWN".equalsIgnoreCase(status)) {
                            finished = true;
                            System.out.println("任务完成，最终结果: ");
                            System.out.println(queryResponse);
                        }
                    } else {
                        System.out.println("查询返回内容: " + queryResponse);
                    }
                }
            } catch (IOException e) {
                e.printStackTrace();
                return;
            }
        }
    }

    static class ApiResponse {
        @SerializedName("request_id")
        String requestId;
        Output output;
    }

    static class Output {
        @SerializedName("task_id")
        String taskId;
        @SerializedName("task_status")
        String taskStatus;
    }
}
```

## Python

```
import os
import time
import requests
import json

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/asr/transcription
API_URL_SUBMIT = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/tasks/
API_URL_QUERY_BASE = "https://dashscope.aliyuncs.com/api/v1/tasks/"


def main():
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key = os.getenv("DASHSCOPE_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }

    # 1. 提交任务
    payload = {
        "model": "qwen3-asr-flash-filetrans",
        "input": {
            "file_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
        },
        "parameters": {
            "channel_id": [0],
            # "language": "zh",
            "enable_itn": False,
            "enable_words": True
        }
    }

    print("提交 ASR 转写任务...")
    try:
        submit_resp = requests.post(API_URL_SUBMIT, headers=headers, data=json.dumps(payload))
    except requests.RequestException as e:
        print(f"请求提交任务失败: {e}")
        return

    if submit_resp.status_code != 200:
        print(f"任务提交失败! HTTP code: {submit_resp.status_code}")
        print(submit_resp.text)
        return

    resp_data = submit_resp.json()
    output = resp_data.get("output")
    if not output or "task_id" not in output:
        print("提交返回内容异常:", resp_data)
        return

    task_id = output["task_id"]
    print(f"任务已提交，task_id: {task_id}")

    # 2. 轮询任务状态
    finished = False
    while not finished:
        time.sleep(2)  # 等待 2 秒再查询

        query_url = API_URL_QUERY_BASE + task_id
        try:
            query_resp = requests.get(query_url, headers=headers)
        except requests.RequestException as e:
            print(f"请求查询任务失败: {e}")
            return

        if query_resp.status_code != 200:
            print(f"查询任务失败! HTTP code: {query_resp.status_code}")
            print(query_resp.text)
            return

        query_data = query_resp.json()
        output = query_data.get("output")
        if output and "task_status" in output:
            status = output["task_status"]
            print(f"当前任务状态: {status}")

            if status.upper() in ("SUCCEEDED", "FAILED", "UNKNOWN"):
                finished = True
                print("任务完成，最终结果如下：")
                print(json.dumps(query_data, indent=2, ensure_ascii=False))
        else:
            print("查询返回内容:", query_data)


if __name__ == "__main__":
    main()
```

## Java SDK

```
import com.alibaba.dashscope.audio.qwen_asr.*;
import com.alibaba.dashscope.utils.Constants;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;

public class Main {
    public static void main(String[] args) {
        // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1
        Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
        QwenTranscriptionParam param =
                QwenTranscriptionParam.builder()
                        // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                        // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                        .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                        .model("qwen3-asr-flash-filetrans")
                        .fileUrl("https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav")
                        //.parameter("language", "zh")
                        //.parameter("channel_id", new ArrayList<String>(){{add("0");add("1");}})
                        .parameter("enable_itn", false)
                        .parameter("enable_words", true)
                        .build();
        try {
            QwenTranscription transcription = new QwenTranscription();
            // 提交任务
            QwenTranscriptionResult result = transcription.asyncCall(param);
            System.out.println("create task result: " + result);
            // 查询任务状态
            result = transcription.fetch(QwenTranscriptionQueryParam.FromTranscriptionParam(param, result.getTaskId()));
            System.out.println("task status: " + result);
            // 等待任务完成
            result =
                    transcription.wait(
                            QwenTranscriptionQueryParam.FromTranscriptionParam(param, result.getTaskId()));
            System.out.println("task result: " + result);
            // 获取语音识别结果
            QwenTranscriptionTaskResult taskResult = result.getResult();
            if (taskResult != null) {
                // 获取识别结果的url
                String transcriptionUrl = taskResult.getTranscriptionUrl();
                // 获取url内对应的结果
                HttpURLConnection connection =
                        (HttpURLConnection) new URL(transcriptionUrl).openConnection();
                connection.setRequestMethod("GET");
                connection.connect();
                BufferedReader reader =
                        new BufferedReader(new InputStreamReader(connection.getInputStream()));
                // 格式化输出json结果
                Gson gson = new GsonBuilder().setPrettyPrinting().create();
                System.out.println(gson.toJson(gson.fromJson(reader, JsonObject.class)));
            }
        } catch (Exception e) {
            System.out.println("error: " + e);
        }
    }
}
```

## Python SDK

```
import json
import os
import sys
from http import HTTPStatus

import dashscope
from dashscope.audio.qwen_asr import QwenTranscription
from dashscope.api_entities.dashscope_response import TranscriptionResponse


# run the transcription script
if __name__ == '__main__':
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

    # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1
    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
    task_response = QwenTranscription.async_call(
        model='qwen3-asr-flash-filetrans',
        file_url='https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav',
        #language="",
        enable_itn=False,
        enable_words=True
    )
    print(f'task_response: {task_response}')
    print(task_response.output.task_id)
    query_response = QwenTranscription.fetch(task=task_response.output.task_id)
    print(f'query_response: {query_response}')
    task_result = QwenTranscription.wait(task=task_response.output.task_id)
    print(f'task_result: {task_result}')
```

## 千问3-ASR-Flash

千问3-ASR-Flash模型支持最长5分钟录音。该模型可输入公网可访问的音频文件URL或直接上传本地文件。此外，它可流式返回识别结果。

## 输入内容：音频文件URL

## Python SDK

```
import os
import dashscope

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

messages = [
    {"role": "user", "content": [{"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}]}
]

response = dashscope.MultiModalConversation.call(
    # 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        # "language": "zh", # 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        "enable_itn":False
    }
)
print(response)
```

## Java SDK

```
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.Constants;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("audio", "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3")))
                .build();

        MultiModalMessage sysMessage = MultiModalMessage.builder().role(Role.SYSTEM.getValue())
                .build();

        Map<String, Object> asrOptions = new HashMap<>();
        asrOptions.put("enable_itn", false);
        // asrOptions.put("language", "zh"); // 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
                .model("qwen3-asr-flash")
                .message(sysMessage)
                .message(userMessage)
                .parameter("asr_options", asrOptions)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
            Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## cURL

```
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
# 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若使用美国地域的模型，需要加us后缀
# === 执行时请删除该注释 ===

curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "qwen3-asr-flash",
    "input": {
        "messages": [
            {
                "content": [
                    {
                        "text": ""
                    }
                ],
                "role": "system"
            },
            {
                "content": [
                    {
                        "audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                    }
                ],
                "role": "user"
            }
        ]
    },
    "parameters": {
        "asr_options": {
            "enable_itn": false
        }
    }
}'
```

## 输入内容：Base64编码的音频文件

可输入Base64编码数据（[Data URL](https://www.rfc-editor.org/rfc/rfc2397)），格式为：`data:<mediatype>;base64,<data>`。

-   `<mediatype>`：MIME类型
    
    因音频格式而异，例如：
    
    -   WAV：`audio/wav`
        
    -   MP3：`audio/mpeg`
        
-   `<data>`：音频转成的Base64编码的字符串
    
    Base64编码会增大体积，请控制原文件大小，确保编码后仍符合输入音频大小限制（10MB）
    
-   示例：`data:audio/wav;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//PAxABQ/BXRbMPe4IQAhl9`
    
    **点击查看示例代码**
    
    Python
    
    ```
    import base64, pathlib
    
    # input.mp3为用于声音复刻的本地音频文件，请替换为自己的音频文件路径，确保其符合音频要求
    file_path = pathlib.Path("input.mp3")
    base64_str = base64.b64encode(file_path.read_bytes()).decode()
    data_uri = f"data:audio/mpeg;base64,{base64_str}"
    ```
    
    Java
    
    ```
    import java.nio.file.*;
    import java.util.Base64;
    
    public class Main {
        /**
         * filePath为用于声音复刻的本地音频文件，请替换为自己的音频文件路径，确保其符合音频要求
         */
        public static String toDataUrl(String filePath) throws Exception {
            byte[] bytes = Files.readAllBytes(Paths.get(filePath));
            String encoded = Base64.getEncoder().encodeToString(bytes);
            return "data:audio/mpeg;base64," + encoded;
        }
    
        // 使用示例
        public static void main(String[] args) throws Exception {
            System.out.println(toDataUrl("input.mp3"));
        }
    }
    ```
    

## Python SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
import base64
import dashscope
import os
import pathlib

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

# 请替换为实际的音频文件路径
file_path = "welcome.mp3"
# 请替换为实际的音频文件MIME类型
audio_mime_type = "audio/mpeg"

file_path_obj = pathlib.Path(file_path)
if not file_path_obj.exists():
    raise FileNotFoundError(f"音频文件不存在: {file_path}")

base64_str = base64.b64encode(file_path_obj.read_bytes()).decode()
data_uri = f"data:{audio_mime_type};base64,{base64_str}"

messages = [
    {"role": "user", "content": [{"audio": data_uri}]}
]
response = dashscope.MultiModalConversation.call(
    # 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        # "language": "zh", # 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        "enable_itn":False
    }
)
print(response)
```

## Java SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.Constants;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    // 请替换为实际的音频文件路径
    private static final String AUDIO_FILE = "welcome.mp3";
    // 请替换为实际的音频文件MIME类型
    private static final String AUDIO_MIME_TYPE = "audio/mpeg";

    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException, IOException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("audio", toDataUrl())))
                .build();

        MultiModalMessage sysMessage = MultiModalMessage.builder().role(Role.SYSTEM.getValue())
                .build();

        Map<String, Object> asrOptions = new HashMap<>();
        asrOptions.put("enable_itn", false);
        // asrOptions.put("language", "zh"); // 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
                .model("qwen3-asr-flash")
                .message(sysMessage)
                .message(userMessage)
                .parameter("asr_options", asrOptions)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }

    public static void main(String[] args) {
        try {
            // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
            Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException | IOException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }

    // 生成 data URI
    public static String toDataUrl() throws IOException {
        byte[] bytes = Files.readAllBytes(Paths.get(AUDIO_FILE));
        String encoded = Base64.getEncoder().encodeToString(bytes);
        return "data:" + AUDIO_MIME_TYPE + ";base64," + encoded;
    }
}
```

## 输入内容：本地音频文件绝对路径

使用DashScope SDK处理本地图像文件时，需要传入文件路径。请您参考下表，结合您的使用方式与操作系统进行文件路径的创建。

| **系统** | **SDK** | **传入的文件路径** | **示例** |
| --- | --- | --- | --- |
| Linux或macOS系统 | Python SDK | file://{文件的绝对路径} | file:///home/images/test.png |
| Java SDK |
| Windows系统 | Python SDK | file://{文件的绝对路径} | file://D:/images/test.png |
| Java SDK | file:///{文件的绝对路径} | file:///D:images/test.png |

**重要**

使用本地文件时，接口调用上限为 100 QPS，且不支持扩容，请勿用于生产环境、高并发及压测场景；如需更高并发，建议将文件上传至 OSS 并通过录音文件 URL 方式调用。

## Python SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
import os
import dashscope

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

# 请用您的本地音频的绝对路径替换 ABSOLUTE_PATH/welcome.mp3
audio_file_path = "file://ABSOLUTE_PATH/welcome.mp3"

messages = [
    {"role": "user", "content": [{"audio": audio_file_path}]}
]
response = dashscope.MultiModalConversation.call(
    # 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        # "language": "zh", # 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        "enable_itn":False
    }
)
print(response)
```

## Java SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.Constants;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        // 请用您本地文件的绝对路径替换掉ABSOLUTE_PATH/welcome.mp3
        String localFilePath = "file://ABSOLUTE_PATH/welcome.mp3";
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("audio", localFilePath)))
                .build();

        MultiModalMessage sysMessage = MultiModalMessage.builder().role(Role.SYSTEM.getValue())
                .build();

        Map<String, Object> asrOptions = new HashMap<>();
        asrOptions.put("enable_itn", false);
        // asrOptions.put("language", "zh"); // 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
                .model("qwen3-asr-flash")
                .message(sysMessage)
                .message(userMessage)
                .parameter("asr_options", asrOptions)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
            Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## 流式输出

模型并不是一次性生成最终结果，而是逐步地生成中间结果，最终结果由中间结果拼接而成。使用非流式输出方式需要等待模型生成结束后再将生成的中间结果拼接后返回，而流式输出可以实时地将中间结果返回，您可以在模型进行输出的同时进行阅读，减少等待模型回复的时间。您可以根据调用方式来设置不同的参数以实现流式输出：

-   DashScope Python SDK方式：设置`stream`参数为true。
    
-   DashScope Java SDK方式：需要通过`streamCall`接口调用。
    
-   DashScope HTTP方式：需要在Header中指定`X-DashScope-SSE`为`enable`。
    

## Python SDK

```
import os
import dashscope

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

messages = [
    {"role": "user", "content": [{"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}]}
]
response = dashscope.MultiModalConversation.call(
    # 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        # "language": "zh", # 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        "enable_itn":False
    },
    stream=True
)

for response in response:
    try:
        print(response["output"]["choices"][0]["message"].content[0]["text"])
    except:
        pass
```

## Java SDK

```
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.Constants;
import io.reactivex.Flowable;

public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("audio", "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3")))
                .build();

        MultiModalMessage sysMessage = MultiModalMessage.builder().role(Role.SYSTEM.getValue())
                .build();

        Map<String, Object> asrOptions = new HashMap<>();
        asrOptions.put("enable_itn", false);
        // asrOptions.put("language", "zh"); // 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 若使用美国地域的模型，需在模型后面加上“-us”后缀，例如qwen3-asr-flash-us
                .model("qwen3-asr-flash")
                .message(sysMessage)
                .message(userMessage)
                .parameter("asr_options", asrOptions)
                .build();
        Flowable<MultiModalConversationResult> resultFlowable = conv.streamCall(param);
        resultFlowable.blockingForEach(item -> {
            try {
                System.out.println(item.getOutput().getChoices().get(0).getMessage().getContent().get(0).get("text"));
            } catch (Exception e){
                System.exit(0);
            }
        });
    }

    public static void main(String[] args) {
        try {
            // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1
            Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## cURL

```
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation，若使用美国地域的模型，需将url替换为：https://dashscope-us.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
# 新加坡/美国地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若使用美国地域的模型，需要加us后缀
# === 执行时请删除该注释 ===

curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-H "X-DashScope-SSE: enable" \
-d '{
    "model": "qwen3-asr-flash",
    "input": {
        "messages": [
            {
                "content": [
                    {
                        "text": ""
                    }
                ],
                "role": "system"
            },
            {
                "content": [
                    {
                        "audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                    }
                ],
                "role": "user"
            }
        ]
    },
    "parameters": {
        "incremental_output": true,
        "asr_options": {
            "enable_itn": false
        }
    }
}'
```

**千问Audio ASR**

千问Audio ASR模型为Beta版本，功能有限，且不保证服务稳定，仅供体验。生产环境请务必使用千问3-ASR-Flash-Filetrans或千问3-ASR-Flash。

## 输入内容：音频文件URL

## Python SDK

```
import dashscope

messages = [{"role": "user","content": [{"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}]}]
response = dashscope.MultiModalConversation.call(
    model="qwen-audio-asr",
    messages=messages,
    result_format="message")
print(response)
```

## Java SDK

```
import java.util.Arrays;
import java.util.Collections;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.JsonUtils;
public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("audio", "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3")))
                .build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                .model("qwen-audio-asr")
                .message(userMessage)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## cURL

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "qwen-audio-asr",
    "input":{
        "messages":[
            {
                "role": "user",
                "content": [
                    {"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}
                ]
            }
        ]
    }
}'
```

## 输入内容：本地音频文件绝对路径

使用DashScope SDK处理本地图像文件时，需要传入文件路径。请您参考下表，结合您的使用方式与操作系统进行文件路径的创建。

| **系统** | **SDK** | **传入的文件路径** | **示例** |
| --- | --- | --- | --- |
| Linux或macOS系统 | Python SDK | file://{文件的绝对路径} | file:///home/images/test.png |
| Java SDK |
| Windows系统 | Python SDK | file://{文件的绝对路径} | file://D:/images/test.png |
| Java SDK | file:///{文件的绝对路径} | file:///D:images/test.png |

**重要**

使用本地文件时，接口调用上限为 100 QPS，且不支持扩容，请勿用于生产环境、高并发及压测场景；如需更高并发，建议将文件上传至 OSS 并通过录音文件 URL 方式调用。

## Python SDK

```
from dashscope import MultiModalConversation

# 请用您的本地音频的绝对路径替换 ABSOLUTE_PATH/welcome.mp3
audio_file_path = "file://ABSOLUTE_PATH/welcome.mp3"
messages = [{"role": "user","content": [{"audio": audio_file_path}]}]

response = MultiModalConversation.call(model="qwen-audio-asr", messages=messages)
print(response)
```

## Java SDK

```
import java.util.Arrays;
import java.util.HashMap;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    public static void callWithLocalFile()
            throws ApiException, NoApiKeyException, UploadFileException {
        // 请用您本地文件的绝对路径替换掉ABSOLUTE_PATH/welcome.mp3
        String localFilePath = "file://ABSOLUTE_PATH/welcome.mp3";
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder().role(Role.USER.getValue())
                .content(Arrays.asList(new HashMap<String, Object>(){{put("audio", localFilePath);}}
                ))
                .build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                .model("qwen-audio-asr")
                .message(userMessage)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            callWithLocalFile();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## 流式输出

模型并不是一次性生成最终结果，而是逐步地生成中间结果，最终结果由中间结果拼接而成。使用非流式输出方式需要等待模型生成结束后再将生成的中间结果拼接后返回，而流式输出可以实时地将中间结果返回，您可以在模型进行输出的同时进行阅读，减少等待模型回复的时间。您可以根据调用方式来设置不同的参数以实现流式输出：

-   DashScope Python SDK方式：设置`stream`参数为true。
    
-   DashScope Java SDK方式：需要通过`streamCall`接口调用。
    
-   DashScope HTTP方式：需要在Header中指定`X-DashScope-SSE`为`enable`。
    

## Python SDK

```
import dashscope

messages = [{"role": "user","content": [{"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}]}]

response = dashscope.MultiModalConversation.call(
    model="qwen-audio-asr",
    messages=messages,
    result_format="message",
    stream=True
    )
full_content = ""
print("流式输出内容为：")
for response in response:
    try:
        print(response["output"]["choices"][0]["message"].content[0]["text"])
        full_content += response["output"]["choices"][0]["message"].content[0]["text"]
    except:
        pass
print(f"完整内容为：{full_content}")
```

## Java SDK

```
import java.util.Arrays;
import java.util.HashMap;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import io.reactivex.Flowable;

public class Main {
    public static void streamCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        // must create mutable map.
        MultiModalMessage userMessage = MultiModalMessage.builder().role(Role.USER.getValue())
                .content(Arrays.asList(new HashMap<String, Object>(){{put("audio", "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3");}}
                )).build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                .model("qwen-audio-asr")
                .message(userMessage)
                .incrementalOutput(true)
                .build();
        Flowable<MultiModalConversationResult> result = conv.streamCall(param);
        result.blockingForEach(item -> {
            try {
                System.out.println(item.getOutput().getChoices().get(0).getMessage().getContent().get(0).get("text"));
            } catch (Exception e){
                System.exit(0);
            }
        });
    }

    public static void main(String[] args) {
        try {
            streamCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}
```

## cURL

```
curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-H "X-DashScope-SSE: enable" \
-d '{
    "model": "qwen-audio-asr",
    "input":{
        "messages":[
            {
                "role": "user",
                "content": [
                    {"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"}
                ]
            }
        ]
    },
    "parameters": {
      "incremental_output": true
    }
}'
```

## OpenAI兼容

仅千问3-ASR-Flash系列模型支持OpenAI兼容方式调用。OpenAI兼容方式仅允许输入公网可访问的音频文件URL，不支持输入本地音频文件绝对路径。

OpenAI Python SDK 版本应不低于1.52.0， Node.js SDK 版本应不低于 4.68.0。

`asr_options`非OpenAI标准参数，若使用OpenAI SDK，请通过`extra_body`传入。

## 输入内容：音频文件URL

## Python SDK

```
from openai import OpenAI
import os

try:
    client = OpenAI(
        # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    

    stream_enabled = False  # 是否开启流式输出
    completion = client.chat.completions.create(
        model="qwen3-asr-flash",
        messages=[
            {
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                        }
                    }
                ],
                "role": "user"
            }
        ],
        stream=stream_enabled,
        # stream设为False时，不能设置stream_options参数
        # stream_options={"include_usage": True},
        extra_body={
            "asr_options": {
                # "language": "zh",
                "enable_itn": False
            }
        }
    )
    if stream_enabled:
        full_content = ""
        print("流式输出内容为：")
        for chunk in completion:
            # 如果stream_options.include_usage为True，则最后一个chunk的choices字段为空列表，需要跳过（可以通过chunk.usage获取 Token 使用量）
            print(chunk)
            if chunk.choices and chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
        print(f"完整内容为：{full_content}")
    else:
        print(f"非流式输出内容为：{completion.choices[0].message.content}")
except Exception as e:
    print(f"错误信息：{e}")
```

## Node.js SDK

```
// 运行前的准备工作:
// Windows/Mac/Linux 通用:
// 1. 确保已安装 Node.js (建议版本 >= 14)
// 2. 运行以下命令安装必要的依赖: npm install openai

import OpenAI from "openai";

const client = new OpenAI({
  // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
  // 若没有配置环境变量，请用百炼API Key将下行替换为：apiKey: "sk-xxx",
  apiKey: process.env.DASHSCOPE_API_KEY,
  // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  baseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1", 
});

async function main() {
  try {
    const streamEnabled = false; // 是否开启流式输出
    const completion = await client.chat.completions.create({
      model: "qwen3-asr-flash",
      messages: [
        {
          role: "user",
          content: [
            {
              type: "input_audio",
              input_audio: {
                data: "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
              }
            }
          ]
        }
      ],
      stream: streamEnabled,
      // stream设为False时，不能设置stream_options参数
      // stream_options: {
      //   "include_usage": true
      // },
      extra_body: {
        asr_options: {
          // language: "zh",
          enable_itn: false
        }
      }
    });

    if (streamEnabled) {
      let fullContent = "";
      console.log("流式输出内容为：");
      for await (const chunk of completion) {
        console.log(JSON.stringify(chunk));
        if (chunk.choices && chunk.choices.length > 0) {
          const delta = chunk.choices[0].delta;
          if (delta && delta.content) {
            fullContent += delta.content;
          }
        }
      }
      console.log(`完整内容为：${fullContent}`);
    } else {
      console.log(`非流式输出内容为：${completion.choices[0].message.content}`);
    }
  } catch (err) {
    console.error(`错误信息：${err}`);
  }
}

main();
```

## cURL

```
# ======= 重要提示 =======
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
# 新加坡地域和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "qwen3-asr-flash",
    "messages": [
        {
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
                    }
                }
            ],
            "role": "user"
        }
    ],
    "stream":false,
    "asr_options": {
        "enable_itn": false
    }
}'
```

## 输入内容：Base64编码的音频文件

可输入Base64编码数据（[Data URL](https://www.rfc-editor.org/rfc/rfc2397)），格式为：`data:<mediatype>;base64,<data>`。

-   `<mediatype>`：MIME类型
    
    因音频格式而异，例如：
    
    -   WAV：`audio/wav`
        
    -   MP3：`audio/mpeg`
        
-   `<data>`：音频转成的Base64编码的字符串
    
    Base64编码会增大体积，请控制原文件大小，确保编码后仍符合输入音频大小限制（10MB）
    
-   示例：`data:audio/wav;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//PAxABQ/BXRbMPe4IQAhl9`
    
    **点击查看示例代码**
    
    Python
    
    ```
    import base64, pathlib
    
    # input.mp3为用于声音复刻的本地音频文件，请替换为自己的音频文件路径，确保其符合音频要求
    file_path = pathlib.Path("input.mp3")
    base64_str = base64.b64encode(file_path.read_bytes()).decode()
    data_uri = f"data:audio/mpeg;base64,{base64_str}"
    ```
    
    Java
    
    ```
    import java.nio.file.*;
    import java.util.Base64;
    
    public class Main {
        /**
         * filePath为用于声音复刻的本地音频文件，请替换为自己的音频文件路径，确保其符合音频要求
         */
        public static String toDataUrl(String filePath) throws Exception {
            byte[] bytes = Files.readAllBytes(Paths.get(filePath));
            String encoded = Base64.getEncoder().encodeToString(bytes);
            return "data:audio/mpeg;base64," + encoded;
        }
    
        // 使用示例
        public static void main(String[] args) throws Exception {
            System.out.println(toDataUrl("input.mp3"));
        }
    }
    ```
    

## Python SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
import base64
from openai import OpenAI
import os
import pathlib

try:
    # 请替换为实际的音频文件路径
    file_path = "welcome.mp3"
    # 请替换为实际的音频文件MIME类型
    audio_mime_type = "audio/mpeg"

    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    base64_str = base64.b64encode(file_path_obj.read_bytes()).decode()
    data_uri = f"data:{audio_mime_type};base64,{base64_str}"

    client = OpenAI(
        # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    

    stream_enabled = False  # 是否开启流式输出
    completion = client.chat.completions.create(
        model="qwen3-asr-flash",
        messages=[
            {
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": data_uri
                        }
                    }
                ],
                "role": "user"
            }
        ],
        stream=stream_enabled,
        # stream设为False时，不能设置stream_options参数
        # stream_options={"include_usage": True},
        extra_body={
            "asr_options": {
                # "language": "zh",
                "enable_itn": False
            }
        }
    )
    if stream_enabled:
        full_content = ""
        print("流式输出内容为：")
        for chunk in completion:
            # 如果stream_options.include_usage为True，则最后一个chunk的choices字段为空列表，需要跳过（可以通过chunk.usage获取 Token 使用量）
            print(chunk)
            if chunk.choices and chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
        print(f"完整内容为：{full_content}")
    else:
        print(f"非流式输出内容为：{completion.choices[0].message.content}")
except Exception as e:
    print(f"错误信息：{e}")
```

## Node.js SDK

示例中用到的音频文件为：[welcome.mp3](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20260105/wotsae/welcome.mp3)。

```
// 运行前的准备工作:
// Windows/Mac/Linux 通用:
// 1. 确保已安装 Node.js (建议版本 >= 14)
// 2. 运行以下命令安装必要的依赖: npm install openai

import OpenAI from "openai";
import { readFileSync } from 'fs';

const client = new OpenAI({
  // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
  // 若没有配置环境变量，请用百炼API Key将下行替换为：apiKey: "sk-xxx",
  apiKey: process.env.DASHSCOPE_API_KEY,
  // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  baseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1", 
});

const encodeAudioFile = (audioFilePath) => {
    const audioFile = readFileSync(audioFilePath);
    return audioFile.toString('base64');
};

// 请替换为实际的音频文件路径
const dataUri = `data:audio/mpeg;base64,${encodeAudioFile("welcome.mp3")}`;

async function main() {
  try {
    const streamEnabled = false; // 是否开启流式输出
    const completion = await client.chat.completions.create({
      model: "qwen3-asr-flash",
      messages: [
        {
          role: "user",
          content: [
            {
              type: "input_audio",
              input_audio: {
                data: dataUri
              }
            }
          ]
        }
      ],
      stream: streamEnabled,
      // stream设为False时，不能设置stream_options参数
      // stream_options: {
      //   "include_usage": true
      // },
      extra_body: {
        asr_options: {
          // language: "zh",
          enable_itn: false
        }
      }
    });

    if (streamEnabled) {
      let fullContent = "";
      console.log("流式输出内容为：");
      for await (const chunk of completion) {
        console.log(JSON.stringify(chunk));
        if (chunk.choices && chunk.choices.length > 0) {
          const delta = chunk.choices[0].delta;
          if (delta && delta.content) {
            fullContent += delta.content;
          }
        }
      }
      console.log(`完整内容为：${fullContent}`);
    } else {
      console.log(`非流式输出内容为：${completion.choices[0].message.content}`);
    }
  } catch (err) {
    console.error(`错误信息：${err}`);
  }
}

main();
```

## **API参考**

[录音文件识别-千问API参考](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)

## **模型应用上架及备案**

参见[应用合规备案](https://help.aliyun.com/zh/model-studio/compliance-and-launch-filing-guide-for-ai-apps-powered-by-the-tongyi-model)。

## **模型功能特性对比**

下表中qwen3-asr-flash和qwen3-asr-flash-2025-09-08模型的功能特性同样适用于美国（弗吉尼亚）地域对应的qwen3-asr-flash-us和qwen3-asr-flash-2025-09-08-us模型。

| **功能/特性** | **qwen3-asr-flash-filetrans、qwen3-asr-flash-filetrans-2025-11-17** | **qwen3-asr-flash、qwen3-asr-flash-2026-02-10、qwen3-asr-flash-2025-09-08** | **qwen-audio-asr** |
| --- | --- | --- | --- |
| **支持语言** | 中文（普通话、四川话、闽南语、吴语、粤语）、英语、日语、德语、韩语、俄语、法语、葡萄牙语、阿拉伯语、意大利语、西班牙语、印地语、印尼语、泰语、土耳其语、乌克兰语、越南语、捷克语、丹麦语、菲律宾语、芬兰语、冰岛语、马来语、挪威语、波兰语、瑞典语 |   | 中文、英文 |
| **支持的音频格式** | aac、amr、avi、flac、flv、m4a、mkv、mov、mp3、mp4、mpeg、ogg、opus、wav、webm、wma、wmv | aac、amr、avi、aiff、flac、flv、mkv、mp3、mpeg、ogg、opus、wav、webm、wma、wmv | aac、amr、avi、aiff、flac、flv、m4a、mkv、mp3、mpeg、ogg、opus、wav、webm、wma、wmv |
| **采样率** | 因音频格式而异： - pcm格式音频：16kHz - 其他格式音频：任意（服务端会先将音频重采样为 16 kHz，再进行识别） |   | 16kHz |
| **声道** | 任意 不同模型在处理多声道音频时方式存在差异： - 千问3-ASR-Flash-Filetrans：需通过`channel_id`参数指定音轨索引 - 千问3-ASR-Flash：无需额外处理，模型会对多声道音频做均值合并后再处理 |   | 单声道 |
| **输入形式** | 公网可访问的待识别文件URL | Base64编码的文件、本地文件绝对路径、公网可访问的待识别文件URL | 本地文件绝对路径、公网可访问的待识别文件URL |
| **音频大小/时长** | 音频文件大小不超过2GB，且时长不超过12小时 | 音频文件大小不超过10MB，且时长不超过5分钟 | 音频文件大小不超过10MB，且时长不超过3分钟 |
| **情感识别** | 支持 固定开启，可通过响应参数`emotion`查看结果 |   | 不支持 |
| **时间戳** | 支持 固定开启，可通过请求参数`enable_words`控制时间戳级别 > 字级别时间戳仅支持以下语种：中文、英语、日语、韩语、德语、法语、西班牙语、意大利语、葡萄牙语、俄语，其他语种可能无法保证准确性 | 不支持 |   |
| **标点符号预测** | 支持 固定开启 |   | 不支持 |
| **ITN** | 支持 默认关闭，可开启，仅适用于中、英文 |   | 不支持 |
| **歌唱识别** | 支持 固定开启 |   | 不支持 |
| **噪声拒识** | 支持 固定开启 |   | 不支持 |
| **敏感词过滤** | 不支持 |   |   |
| **说话人分离** | 不支持 |   |   |
| **语气词过滤** | 不支持 |   |   |
| **VAD** | 支持 固定开启 | 不支持 |   |
| **限流（RPM）** | 100 |   |   |
| **接入方式** | DashScope：Java/Python SDK、RESTful API | DashScope：Java/Python SDK、RESTful API OpenAI：Python/Node.js SDK、RESTful API | DashScope：Java/Python SDK、RESTful API |
| **价格** | 中国内地：0.00022元/秒 美国：0.000035元/秒 国际：0.00026元/秒 |   | 目前仅供免费体验 > 免费额度用完后不可调用，推荐使用 Qwen3 ASR |

## 常见问题

### **Q：如何为API提供公网可访问的音频URL？**

推荐使用[阿里云对象存储OSS](https://help.aliyun.com/zh/oss/user-guide/simple-upload#a632b50f190j8)，它提供了高可用、高可靠的存储服务，并且可以方便地生成公网访问URL。

**在公网环境下验证生成的 URL 可正常访问：**可在浏览器或通过 curl 命令访问该 URL，确保音频文件能够成功下载或播放（HTTP状态码为200）。

### **Q：如何检查音频格式是否符合要求？**

可以使用开源工具[ffprobe](https://ffmpeg.org/ffprobe.html)快速获取音频的详细信息：

```
# 查询音频的容器格式(format_name)、编码(codec_name)、采样率(sample_rate)、声道数(channels)
ffprobe -v error -show_entries format=format_name -show_entries stream=codec_name,sample_rate,channels -of default=noprint_wrappers=1 your_audio_file.mp3
```

### **Q：**如何处理音频以满足模型要求？

可以使用开源工具[FFmpeg](https://ffmpeg.en.lo4d.com/download)对音频进行裁剪或格式转换：

-   **音频裁剪：从长音频中截取片段**
    
    ```
    # -i: 输入文件
    # -ss 00:01:30: 设置裁剪的起始时间 (从1分30秒开始)
    # -t 00:02:00: 设置裁剪的持续时长 (裁剪2分钟)
    # -c copy: 直接复制音频流，不重新编码，速度快
    # output_clip.wav: 输出文件
    ffmpeg -i long_audio.wav -ss 00:01:30 -t 00:02:00 -c copy output_clip.wav
    ```
    
-   **格式转换**
    
    例如，将任意音频转换为16kHz、16-bit、单声道WAV文件
    
    ```
    # -i: 输入文件
    # -ac 1: 设置声道数为1 (单声道)
    # -ar 16000: 设置采样率为16000Hz (16kHz)
    # -sample_fmt s16: 设置采样格式为16-bit signed integer PCM
    # output.wav: 输出文件
    ffmpeg -i input.mp3 -ac 1 -ar 16000 -sample_fmt s16 output.wav
    ```
    

/\* 让引用上下间距调小，避免内容显示过于稀疏 \*/ .unionContainer .markdown-body blockquote { margin: 4px 0; } .aliyun-docs-content table.qwen blockquote { border-left: none; /\* 添加这一行来移除表格里的引用文字的左侧边框 \*/ padding-left: 5px; /\* 左侧内边距 \*/ margin: 4px 0; }

 span.aliyun-docs-icon { color: transparent !important; font-size: 0 !important; } span.aliyun-docs-icon:before { color: black; font-size: 16px; } span.aliyun-docs-icon.icon-size-20:before { font-size: 20px; } span.aliyun-docs-icon.icon-size-22:before { font-size: 22px; } span.aliyun-docs-icon.icon-size-24:before { font-size: 24px; } span.aliyun-docs-icon.icon-size-26:before { font-size: 26px; } span.aliyun-docs-icon.icon-size-28:before { font-size: 28px; }