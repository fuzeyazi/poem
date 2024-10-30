package com.fuze.potryservice.controller.user;

import com.fuze.entity.*;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.*;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.web.bind.annotation.*;

import java.util.*;


@RestController
@RequestMapping("/user/poetry")
@Api(tags ="用户对诗词阁的相关操作")
@Slf4j
public class PoetryController {
@Autowired
private PotryService potryService;


    @ApiOperation(value = "获取古诗的数量")
    @GetMapping("/GetCount")
    public Result<Integer> GetCount(){
        log.info("获取现存古诗数量执行:");
        Integer count=potryService.getcount();
        return Result.success(count);
    }
    @ApiOperation(value = "获取所有古诗的名称")
    @GetMapping("/GetAllPoemName")
    public Result<List<String>>GetAllPoemName(){
        log.info("获取所有古诗名称执行:");
        List<String> list=potryService.GetAllPoemName();
        return Result.success(list);
    }

    @ApiOperation(value = "通过单个id获取古诗的详细信息")
    @GetMapping("/GetContentById/{id}")
    public Result<Poem>GetContentById(@PathVariable Integer id){
        log.info("通过id获取古诗内容执行:");
        Poem poem=potryService.GetContentById(id);
        return Result.success(poem);
    }


    @ApiOperation(value = "查询所有的朝代")
    @GetMapping("/GetAllDynasty")
    public Result<List<String>>GetAllDynasty(){
        log.info("查询所有的朝代执行:");
        List<String> list=potryService.GetAllDynasty();
        return Result.success(list);
    }

    @ApiOperation(value = "获取所有朝代及其对应的古文信息")
    @GetMapping("GetDynastyandpoem")
    public Result<List<DynatryPOemVo>>GetDynastyandpoem(){
        log.info("查询所有的朝代和当时下的古文执行:");
        List<DynatryPoemResultVO> list=potryService.GetDynastyPoemResulVo();

        // 创建一个二维字符串列表，用于存储诗歌数据
        List<List<String>> listpoem = new ArrayList<>();

        // 创建一个DynatryPoemResult类型的列表，用于存储处理后的诗歌信息
        List<DynatryPOemVo> list2 = new ArrayList<>();

        for (DynatryPoemResultVO s : list){
            // 将诗歌标题按逗号分隔，并转换为字符串数组
            String[] split = s.getTitlepoem().split(",");
            // 将字符串数组转换为ArrayList
            List<String> StringList = new ArrayList<>(Arrays.asList(split));
            // 将转换后的标题列表添加到listpoem中（listpoem声明未在代码段中显示）
            listpoem.add(StringList);
            // 使用Builder模式创建一个DynatryPOemVo对象，设置朝代、诗歌数量和标题列表
            DynatryPOemVo ee= DynatryPOemVo.builder().dynasty(s.getDynasty()).poemcount(s.getPoemcount()).titlepoem(StringList).build();
            // 将创建的DynatryPOemVo对象添加到list2中
            list2.add(ee);
        }
        // 返回成功的结果，携带转换后的列表list2
        return Result.success(list2);


    }

    @ApiOperation(value = "根据朝代获取古诗信息")
    @GetMapping("/GetPoemByDynasty/{dynasty}")
    public Result<List<PoemDataVo>>GetPoemByDynasty(@PathVariable String dynasty){
        log.info("根据朝代获取古诗信息执行:");
        List<PoemDataVo> PoemDATAlist=potryService.GetPoemDataVoByDynasty(dynasty);
        log.info("根据朝代获取古诗信息执行:{}",PoemDATAlist);
        return Result.success(PoemDATAlist);
    }

    @ApiOperation(value = "随机返回十条古诗数据")
    @GetMapping("/GetPoemDateRondom")
    public Result<List<PoemDataVo>>GetPoemDateRondom(){
        List<PoemDataVo> list=potryService.GetPoemDateRondom();
        return Result.success(list);
    }

    @ApiOperation(value = "随机获得获得一首诗，今日推荐")
    @GetMapping("/GetVeryGoodPoem")
    public Result<PoemDataVo>GetVeryGoodPoem(){
        return Result.success(potryService.GetVeryGoodPoem());
    }


    @ApiOperation(value = "分页查询古诗（一次获得20条古诗数据）")
    @GetMapping("/GetPoemPage")
    public Result<PageResult> GetPoemPage(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "20") Integer pageSize
    )
    {
        PageResult pageInfo = potryService.GetPoemPage(pageNum, pageSize);
        return Result.success(pageInfo);
    }
    //to 根据诗人查古诗还需要优化
    @ApiOperation(value = "根据诗人查询古诗")
    @GetMapping("/GetPoemByWriter")
    public Result<List<PoemDataVo>>GetPoemByWriter(@RequestParam String name){
        List<PoemDataVo> list=potryService.GetPoemDataVoByWriter(name);
        return Result.success(list);
    }


   @ApiOperation(value = "获取古诗的分类，因为一个古诗不仅仅一个分类,用于前端展示")
    @GetMapping("/GetTypeDotaVo")
   public Result<TypeDateVo> GetTypeDotaVo(){
       List<String> Types=potryService.GetType();

       //进行去重
       Set<String> set=new HashSet<>();
       for (String s:Types){
           String[] bb= s.split(",");
           for (String s1:bb){

               set.add(s1);
           }
       }
//       System.out.println(set);
       TypeDateVo typeDateVo=new TypeDateVo();
       Integer count=set.size();
//       System.out.println(count);
       TypeDateVo typeDateVo1=TypeDateVo.builder().count(count).type(set).build();

//       System.out.println(typeDateVo1);
       return Result.success(typeDateVo1);
    }





    @ApiOperation(value = "通过id跳转到诗的详情页面")
    @GetMapping("/GetPoemContbyid")
    public Result<List<Poem>>GetPoemContent(
            @RequestParam Integer id){
        List<Poem> poem=potryService.GetContentBytitle1(id);
        return Result.success(poem);
    }

    public class SubstringExample {
        public static void main(String[] args) {
            String originalText = "Hello, World! Welcome to Java.";

            // 找到第一个分隔符的位置
            int startIndex = originalText.indexOf("World");

            // 找到第二个分隔符的位置
            int endIndex = originalText.indexOf("Welcome");

            // 如果找到了分隔符
            if (startIndex != -1 && endIndex != -1) {
                // 截取从 "World" 到 "Welcome" 之间的部分
                String subText = originalText.substring(startIndex, endIndex).trim();

                // 输出结果
                System.out.println(subText);  // 输出: World!
            } else {
                System.out.println("分隔符未找到");
            }
        }
    }
//    @ApiOperation(value ="查寻诗人的详细生平事迹")
//    @GetMapping("/GetPoemWriter/{name}")
//    public Result<WriterVo> GetPoemWriter(@PathVariable String name){
//    WriterVo writer=potryService.GetPoemWriter(name);
//    String s=writer.getDetailIntro().replace("\n", "<br>");
//        String[] parts = s.split("\"");
//       String ss= parts[1];
//        System.out.println(ss);
//        String sss= parts[3];
//        System.out.println(sss);
//        System.out.println(parts[5]);
//        System.out.println(parts[7]);
//        writer.setDetailIntro(s);
//        return Result.success(writer);
//    }
@ApiOperation("通过诗人id,返回足够详细的生平事迹")
    @GetMapping("/GetPoemWrier")
    public Result<WriterEndVop> GetPoemWrier(@RequestParam int id){
    WriterEndVo writer=potryService.GetPoemWriter(id);
    String s=writer.getDetailIntro().replace("\n", "<br>");
    String[] parts = s.split("\"");
    List<XiangXi> list=new ArrayList<>();
    int idd=1;
    for (int i = 1; i <parts.length; i=i+4) {
        list.add(XiangXi.builder().
                id(idd++).
                content(parts[i+2]).
                title("<h3>"+parts[i]+ "</h3>").
                build());
        }
    WriterEndVop writerEndVop=WriterEndVop.builder().id(writer.getId()).name(writer.getName()).headImageUrl(writer.getHeadImageUrl()).simpleIntro(writer.getSimpleIntro()).detailIntro(list).build();
        return Result.success( writerEndVop);
    }
@ApiOperation(value = "给朝代名字，返回古诗,做了分页查询")
    @GetMapping("GetPoemBydynasty")
    public Result<PageResult>GetPoemBydynasty(@RequestParam String dynasty,
@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "4") Integer pageSize)
{PageResult pageInfo = potryService.GetPoemBydynastys(pageNum, pageSize,dynasty);
        return Result.success(pageInfo);
    }
    @ApiOperation(value = "根据传回的古诗分类获取古诗信息")
    @GetMapping("/GetPoemByType")
    public  Result<PageResult>GetPoemByType1(
            @RequestParam String Type,
            @RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "4") Integer pageSize)
    {
        PageResult pageInfo = potryService.GetPoemByType(pageNum, pageSize,Type);

        return Result.success(pageInfo);
    }

    @ApiOperation(value = "根据朝代返回诗人的信息")
    @GetMapping("/GetwriterBydynasty")
    public  Result<PageResult>GetwriterBydynasty(
            @RequestParam String dynsaty,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "4") Integer pageSize)
    {
        log.info("dynasty:{}, pageNum:{}, pageSize:{}", dynsaty, pageNum, pageSize);
             PageResult pageInfo = potryService.GetwriterBydynasty(pageNum, pageSize,dynsaty);
        return Result.success(pageInfo);
    }
    @ApiOperation(value = "随机返回十条诗人数据")
    @GetMapping("/Get")
    public  Result<List<Writer>>GetwriterBydynasty()
    {
        List<Writer> list=potryService.GetRondWriter();
        return Result.success(list);
    }
    @ApiOperation(value = "根据诗人返回古诗的信息")
    @GetMapping("/GetwriterBywriter")
    public  Result<PageResult>GetwriterBywriter(
            @RequestParam String writer,
            @RequestParam(defaultValue = "1")
            Integer pageNum, @RequestParam(defaultValue = "4") Integer pageSize)
    {
        log.info("dynasty:{}, pageNum:{}, pageSize:{}", writer, pageNum, pageSize);
        PageResult pageInfo = potryService.GetwriterBydynasty11(pageNum, pageSize,writer);
        return Result.success(pageInfo);
    }

    @ApiOperation(value = "根据诗人返回名句的信息")
    @GetMapping("/GetwriterByThesisDataVo")
    public  Result<PageResult>GetwriterByRhesisDataVo(
            @RequestParam String writer,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize)
    {
        log.info("dynasty:{}, pageNum:{}, pageSize:{}", writer, pageNum, pageSize);
        PageResult pageInfo = potryService.GetwriterBydynasty111(pageNum,pageSize,writer);
        return Result.success(pageInfo);
    }


}



