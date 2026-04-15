> ## Documentation Index
> Fetch the complete documentation index at: https://docs.bigmodel.cn/llms.txt
> Use this file to discover all available pages before exploring further.

# GLM-Image

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/rectangle-list.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 概览 </div>

GLM-Image 是智谱新旗舰图像生成模型， 模型全程基于国产芯片完成训练，采用独创的「自回归+扩散解码器」混合架构，兼顾全局指令理解与局部细节刻画，克服了海报、PPT、科普图等知识密集型场景生成难题，是面向以 Nano Banana Pro 为代表的新一代「认知型生成」技术范式的一次重要探索。

<CardGroup cols={2}>
  <Card title="价格" icon={<svg style={{maskImage: "url(/resource/icon/coins.svg)", WebkitMaskImage: "url(/resource/icon/coins.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
    0.1 元 / 次
  </Card>

  <Card title="输入模态" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-right.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-right.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
    文本（最大输入1000字符）
  </Card>

  <Card title="输出模态" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-left.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-left.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
    图像
  </Card>

  <Card title="多分辨率" icon={<svg style={{maskImage: "url(/resource/icon/images.svg)", WebkitMaskImage: "url(/resource/icon/images.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
    支持 1:1、3:4、4:3、16:9 等
  </Card>
</CardGroup>

<Tip>
  **推荐常用尺寸：** 1280x1280 、 1568x1056 、 1056x1568 、 1472x1088 、 1088x1472 、 1728x960 、 960x1728。

  **自定义参数：** 长宽需在 512px-2048px 范围内，且长宽均需为32的整数倍。
</Tip>

<Info>
  请注意，GLM-Image 模型的输出是图片 URL，您需要通过 URL 下载图片。
</Info>

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/stars.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 推荐场景 </div>

<AccordionGroup>
  <Accordion title="商业海报">
    能够生成构图完整、视觉层次清晰、整体设计感突出的节日海报与商业宣传图片，并支持文字内容的精准嵌入与稳定呈现，适用于品牌传播、市场推广等多种商业场景。
  </Accordion>

  <Accordion title="科普插画">
    更擅长绘制包含复杂逻辑关系、流程说明与文字注释的科普插画和原理示意图，能够在保证画面美观的同时，清晰、准确地传达知识结构与核心信息。
  </Accordion>

  <Accordion title="多格图画">
    在生成电商展示图、故事漫画等多格图画时，GLM-Image 可以有效保持整体画风与主体形象的一致性，同时显著提升多处文字生成的准确率，确保内容连贯、表达统一。
  </Accordion>

  <Accordion title="社交媒体图文">
    适用于制作封面设计与版式结构较为复杂的社交媒体图文内容，支持灵活排版与多样化表达，让创作过程更加高效，呈现效果更加丰富多元。
  </Accordion>
</AccordionGroup>

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/gauge-high.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 使用资源 </div>

[体验中心](https://bigmodel.cn/trialcenter/modeltrial/image)：快速测试模型在业务场景上的效果<br />
[接口文档](/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%9B%BE%E5%83%8F%E7%94%9F%E6%88%90)：API 调用方式

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/arrow-up.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 详细介绍 </div>

<Steps>
  <Step title="架构创新：读懂指令，写对文字" titleSize="h3">
    **GLM-image是我们面向「认知型生成」技术范式的一次重要探索，** 这是首个开源的工业表现级离散自回归图像生成模型。

    GLM-Image 引入了「自回归+扩散解码器」混合架构，融合了 9B 的自回归模型与 7B 的 DiT 扩散解码器。前者利用其语言模型的底座优势，专注于提升对指令的语义理解和画面的全局构图；后者配合 Glyph Encoder 的文本编码器，专注于还原图像的高频细节和文字笔画，以此改善模型“提笔忘字”的现象。

    ![Description](https://cdn.bigmodel.cn/markdown/1768305506516image.png?attname=image.png)
    *general pipeline*

    ![Description](https://cdn.bigmodel.cn/markdown/1768305604344image.png?attname=image.png)
    *decoder formulation*
  </Step>

  <Step title="开源 SOTA：更擅长文字密集生成任务" stepNumber={2} titleSize="h3">
    基于上述架构创新，GLM-Image在文字渲染的权威榜单中达到开源 SOTA水平。

    ![Description](https://cdn.bigmodel.cn/markdown/1768308056990image.png?attname=image.png)

    * **CVTG-2K（复杂视觉文字生成）** 榜单核心考察模型在图像中同时生成多处文字的准确性。在多区域文字生成准确率上，GLM-Image 凭借 0.9116 的 Word Accuracy（文字准确率）成绩，位列开源模型前列。在NED（归一化编辑距离）指标上，GLM-Image 同样以 0.9557 胜出，表明其生成的文字与目标文字高度一致，错字、漏字情况更少。
    * **LongText-Bench（长文本渲染）** 榜单考察模型渲染长文本、多行文字的准确性，覆盖招牌、海报、PPT、对话框等8种文字密集场景，并分设中英双语测试，GLM-Image以英文0.9524、中文0.9788的成绩位列开源模型前列。
  </Step>

  <Step title="首个国产芯片训练出的 SOTA 多模态模型" stepNumber={3} titleSize="h3">
    GLM-Image 是我们对国产计算生态的一次深度探索与验证。从早期的数据预处理到最终的大规模预训练，模型构建的全流程均在昇腾Atlas 800T A2设备上完成。

    GLM-Image 是首个在国产芯片上完成全流程训练的SOTA多模态模型，验证了在国产全栈算力底座上训练高性能多模态生成模型的可行性。我们希望这一实践能为社区挖掘国产算力潜力提供有价值的参考。

    ![Description](https://cdn.bigmodel.cn/markdown/1768310696625image.png?attname=image.png)
  </Step>
</Steps>

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/ballot.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 应用示例 </div>

<Tabs>
  <Tab title="科普插画">
    <CardGroup cols={2}>
      <Card title="Prompt" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-right.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-right.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        竖版手工剪贴簿风格的图像。顶部是一条亮红色粗糙撕裂边缘的纸质横幅，用半透明和纸胶带斜着固定，左上角夹着金色回形针，压着一小块写有「首发」的碎纸。横幅上用粗黑体手工剪报风写着主标题「GLM-Image 开源：国产芯片炼出图像生成 SOTA」，标题周围用黑色马克笔画着放射线和手绘画笔调色盘图标。
        背景是拼贴的AI生成图片碎片、芯片电路图纹理、水彩晕染和浅蓝色卡纸。左侧有一个带磨损金属边的数码相框，用透明胶带斜贴，相框内大字写着「自回归 + 扩散解码器」，副标题「9B 自回归理解指令 + 7B DiT 精绘细节」，背景是文字prompt气泡到精美图像的箭头连接图，边缘有手绘箭头标注「读懂指令」「写对文字」。
        右侧散落三张不同颜色的撕裂纸条便利贴，被和纸胶带交叉固定。配有芯片实物照片剪影加华为logo小贴纸、中文艺术字海报截图、多分辨率图像网格等插图。三个撕裂纸条标签带粗黑描边：「昇腾 A2 + 昇思 MindSpore：全程国产训练」「CVTG-2K & LongText-Bench：文字渲染开源第一」「384×384 到 2048×2048：任意比例原生支持」。旁边还有一条窄蓝色撕裂纸条写着「认知型生成：知识 + 推理新范式」，上面有马克笔波浪线和星星。
        底部是一整条深蓝色撕裂纸带，印着电路纹理，用和纸胶带固定。通栏大标题「从"画个图"到"懂你想要什么"的认知型生成引擎」
      </Card>

      <Card title="生成图片" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-left.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-left.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        ![Description](https://cdn.bigmodel.cn/markdown/176832067703920260113-235926.jpeg)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="高质量人像">
    <CardGroup cols={2}>
      <Card title="Prompt" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-right.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-right.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        哈苏胶片质感的画面中，一位长发美女置身于柔和的室内光影里，窗外的枝叶在微风中摇曳，将斑驳的树影投射到她的脸庞和肩头；薄纱轻轻垂落在背景，营造出朦胧唯美的氛围，轮廓光勾勒出她慵懒自然的姿态，凌乱的长发在风中轻轻飘起，发丝在阳光的照射下泛着微光；近景特写捕捉她深情凝望镜头的瞬间，清透细腻的肌肤在高曝光与高明暗的对比中展现丰富的质感，背景略微模糊，泛光与晕染交织出轻柔的梦幻效果，画面带有高噪点的胶片色彩与微妙的反射，整体细节生动，仿佛凝固在午后微风与光影交错的诗意瞬间。
      </Card>

      <Card title="生成图片" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-left.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-left.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        ![Description](https://cdn.bigmodel.cn/markdown/1768310904165image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="社交媒体图文">
    <CardGroup cols={2}>
      <Card title="Prompt" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-right.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-right.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        <br />

        冬季 OOTD 穿搭封面，复古拼贴风：主体是一位女生的主穿搭（浅蓝宽松毛衣 + 黄格衬衫内搭 + 酒红半裙 + 粉白花纹围巾 + 粉调手提包），周围拼贴 2-3 张同系列冬季搭配小图（如蓝羽绒服 + 黑阔腿裤、棕外套 + 藏青裤）；背景融合浅灰方格墙面 + 户外街景局部；添加大尺寸浅蓝艺术字 “OOTD”，手写风标注文字（如 “autumn/win”“work/date”），点缀星星、手绘箭头等小装饰，以及咖啡杯、播放键小图标；整体色调柔和温暖，元素错落排版，营造活泼的冬日穿搭参考感
      </Card>

      <Card title="生成图片" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-left.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-left.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        ![Description](https://cdn.bigmodel.cn/markdown/1768309855615image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="商业海报">
    <CardGroup cols={2}>
      <Card title="Prompt" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-right.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-right.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        <br />

        暗黑艺术感巴宝莉品牌宣传海报：整体采用低饱和深灰色暗调背景，配色以黑白（两匹马）+ 巴宝莉标志性红黑格纹（含白、浅棕线条）为主，文字与 logo 为白色；主体是两匹写实细腻质感的马（左侧纯白、右侧纯黑），头部均被巴宝莉经典红黑格纹丝巾蒙住双眼，丝巾呈现自然垂坠的面料纹理；画面右上角放置白色巴宝莉骑士品牌 logo，底部以大号白色无衬线字体标注 “BURBERRY”；光线为低调柔和的人像光，突出马匹毛发的细腻质感与丝巾的格纹细节，整体风格是高级艺术感的时尚品牌风，氛围神秘且契合品牌经典元素
      </Card>

      <Card title="生成图片" icon={<svg style={{maskImage: "url(/resource/icon/arrow-down-left.svg)", WebkitMaskImage: "url(/resource/icon/arrow-down-left.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} />}>
        ![Description](https://cdn.bigmodel.cn/markdown/1768309771376image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>
</Tabs>

## <div className="flex items-center"> <svg style={{maskImage: "url(/resource/icon/code.svg)", maskRepeat: "no-repeat", maskPosition: "center center",}} className={"h-6 w-6 bg-primary dark:bg-primary-light !m-0 shrink-0"} /> 调用示例 </div>

<Tabs>
  <Tab title="cURL">
    **调用示例**

    ```bash  theme={null}
    curl -X POST "https://open.bigmodel.cn/api/paas/v4/images/generations" \
        -H "Authorization: Bearer YOUR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "glm-image",
            "prompt": "一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云",
            "size": "1280x1280"
        }'
    ```
  </Tab>

  <Tab title="Python">
    **安装 SDK**

    ```bash  theme={null}
    # 安装最新版本
    pip install zai-sdk
    # 或指定版本
    pip install zai-sdk==0.2.1
    ```

    **验证安装**

    ```python  theme={null}
    import zai
    print(zai.__version__)
    ```

    **调用示例**

    ```python  theme={null}
    from zai import ZhipuAiClient
    client = ZhipuAiClient(api_key="your-api-key")  # 请填写您自己的 APIKey
    response = client.images.generations(
        model="glm-image",  # 请填写您要调用的模型名称
        prompt="一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云",
    )
    print(response.data[0].url)
    ```
  </Tab>

  <Tab title="Java">
    **安装 SDK**

    **Maven**

    ```xml  theme={null}
    <dependency>
        <groupId>ai.z.openapi</groupId>
        <artifactId>zai-sdk</artifactId>
        <version>0.3.2</version>
    </dependency>
    ```

    **Gradle (Groovy)**

    ```groovy  theme={null}
    implementation 'ai.z.openapi:zai-sdk:0.3.2'
    ```

    **调用示例**

    ```java  theme={null}
    import ai.z.openapi.ZhipuAiClient;
    import ai.z.openapi.core.Constants;
    import ai.z.openapi.service.image.CreateImageRequest;
    import ai.z.openapi.service.image.ImageResponse;

    public class GlmImageExample {
        public static void main(String[] args) {
            ZhipuAiClient client = ZhipuAiClient.builder().ofZHIPU().apiKey("YOUR_API_KEY").build();
            // Create image generation request
            CreateImageRequest request = CreateImageRequest.builder()
                .model("glm-image")
                .prompt("一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云")
                .size("1280x1280")
                .build();
            ImageResponse response = client.images().createImage(request);
            System.out.println(response.getData());
        }
    }
    ```
  </Tab>
</Tabs>


Built with [Mintlify](https://mintlify.com).