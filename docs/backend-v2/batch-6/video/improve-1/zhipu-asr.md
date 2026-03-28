> ## Documentation Index
> Fetch the complete documentation index at: https://docs.bigmodel.cn/llms.txt
> Use this file to discover all available pages before exploring further.

# 语音转文本

> 使用 [GLM-ASR-2512](/cn/guide/models/sound-and-video/glm-asr-2512) 模型将音频文件转录为文本，支持多语言和实时流式转录。



## OpenAPI

````yaml /openapi/openapi.json post /paas/v4/audio/transcriptions
openapi: 3.0.1
info:
  title: ZHIPU AI API
  description: ZHIPU AI 接口提供强大的 AI 能力，包括聊天对话、工具调用和视频生成。
  license:
    name: ZHIPU AI 开发者协议和政策
    url: https://chat.z.ai/legal-agreement/terms-of-service
  version: 1.0.0
  contact:
    name: Z.AI 开发者
    url: https://chat.z.ai/legal-agreement/privacy-policy
    email: user_feedback@z.ai
servers:
  - url: https://open.bigmodel.cn/api/
    description: 开放平台服务
security:
  - bearerAuth: []
tags:
  - name: 模型 API
    description: Chat API
  - name: 工具 API
    description: Web Search API
  - name: Agent API
    description: Agent API
  - name: 文件 API
    description: File API
  - name: 知识库 API
    description: Knowledge API
  - name: 实时 API
    description: Realtime API
  - name: 批处理 API
    description: Batch API
  - name: 助理 API
    description: Assistant API
  - name: 智能体 API（旧）
    description: QingLiu Agent API
paths:
  /paas/v4/audio/transcriptions:
    post:
      tags:
        - 模型 API
      summary: 语音转文本
      description: >-
        使用 [GLM-ASR-2512](/cn/guide/models/sound-and-video/glm-asr-2512)
        模型将音频文件转录为文本，支持多语言和实时流式转录。
      requestBody:
        content:
          multipart/form-data:
            schema:
              $ref: '#/components/schemas/AudioTranscriptionRequest'
            example:
              model: glm-asr-2512
              stream: false
        required: true
      responses:
        '200':
          description: 业务处理成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AudioTranscriptionResponse'
            text/event-stream:
              schema:
                $ref: '#/components/schemas/AudioTranscriptionStreamResponse'
        default:
          description: 请求失败。
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
components:
  schemas:
    AudioTranscriptionRequest:
      type: object
      required:
        - file
        - model
      properties:
        file:
          type: string
          format: binary
          description: >-
            需要转录的音频文件，支持上传的音频文件格式：`.wav / .mp3`，规格限制：文件大小 ≤ `25 MB`、音频时长 ≤ `30
            秒`
        file_base64:
          type: string
          description: 音频文件Base64编码。file_base64 和 file 只需要传一个（同时传入以file为准）
        model:
          type: string
          description: 要调用的模型编码
          enum:
            - glm-asr-2512
          default: glm-asr-2512
        prompt:
          type: string
          description: 在长文本场景中，可以提供之前的转录结果作为上下文。建议小于8000字。
        hotwords:
          type: array
          description: 热词表，用于提升特定领域词汇识别率。格式例如["人名","地名"]，建议不超过100个。
          items:
            type: string
          maxItems: 100
        stream:
          type: boolean
          default: false
          description: >-
            该参数在使用同步调用时应设置为`false`或省略。表示模型在生成所有内容后一次性返回所有内容。默认值为`false`。如果设置为`true`，模型将通过标准`Event
            Stream`逐块返回生成的内容。当`Event Stream`结束时，将返回一个`data: [DONE]`消息。
        request_id:
          type: string
          description: 由用户端传递，需要唯一；用于区分每次请求的唯一标识符。如果用户端未提供，平台将默认生成。
        user_id:
          type: string
          description: >-
            终端用户的唯一`ID`，帮助平台对终端用户的非法活动、生成非法不当信息或其他滥用行为进行干预。`ID`长度要求：至少`6`个字符，最多`128`个字符。
    AudioTranscriptionResponse:
      type: object
      properties:
        id:
          type: string
          description: 任务 ID
        created:
          type: integer
          format: int64
          description: 请求创建时间，是以秒为单位的 `Unix` 时间戳
        request_id:
          type: string
          description: 由用户端传递，需要唯一；用于区分每次请求的唯一标识符。如果用户端未提供，平台将默认生成。
        model:
          description: 模型名称
          type: string
        text:
          type: string
          description: 音频转录的完整内容
    AudioTranscriptionStreamResponse:
      type: object
      properties:
        id:
          type: string
          description: 任务 ID
        created:
          type: integer
          format: int64
          description: 请求创建时间，是以秒为单位的 `Unix` 时间戳
        model:
          description: 模型名称
          type: string
        type:
          type: string
          description: 音频转录事件类型，`transcript.text.delta`表示正在转录，`transcript.text.done`表示转录完成
        delta:
          type: string
          description: 模型增量返回的音频转录信息
    Error:
      type: object
      properties:
        error:
          required:
            - code
            - message
          type: object
          properties:
            code:
              type: string
            message:
              type: string
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      description: >-
        使用以下格式进行身份验证：Bearer [<your api
        key>](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)

````

Built with [Mintlify](https://mintlify.com).