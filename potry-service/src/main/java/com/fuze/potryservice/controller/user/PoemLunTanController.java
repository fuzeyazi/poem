package com.fuze.potryservice.controller.user;
import com.fuze.context.BaseContext;
import com.fuze.dto.FourmCommentDto;
import com.fuze.dto.PoemBlogDto;
import com.fuze.potryservice.service.PoemLunTanService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.utils.AliOssUtil;
import com.fuze.vo.*;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/user/luntan")
@Api(tags ="文坛")
@Slf4j
public class PoemLunTanController {
    @Autowired
    private AliOssUtil aliOssUtil;
    @Autowired
    private PoemLunTanService poemLunTanService;

    @PostMapping("updateImage")
    @ApiOperation(value = "上传图片(上传什么都可以)")
    private Result<String> updateImage(@RequestParam MultipartFile file) throws IOException {
        //获取文件名
        String originalFilename = file.getOriginalFilename();
        String dd;
        if (originalFilename != null) {
           dd=originalFilename.substring(originalFilename.lastIndexOf("."));
            byte[] bytes = convert(file);
            String url= aliOssUtil.upload(bytes,"lun/"+ UUID.randomUUID()+dd);
            return Result.success(url);
        }
        return Result.error("上传失败");
    }
   private static byte[] convert(MultipartFile file) throws IOException {
        try (InputStream inputStream = file.getInputStream()) {
            return inputStream.readAllBytes();
        }
    }
    @PostMapping("fabutiezi")
    @ApiOperation(value="发布帖子")
   private  Result<String> fabutiezi(@RequestBody PoemBlogDto poemBlogDto){
        Integer id= BaseContext.getCurrentId().intValue();
        poemLunTanService.fabu(poemBlogDto,id);
        log.info("发布成功");
        return Result.success("发布成功");
   }
    @ApiOperation(value="查看所有按分类帖子")
    @GetMapping("selecttiez")
    private Result<PageResult> selecttiez(
                                            @RequestParam Integer type1,
                                           @RequestParam(defaultValue = "1") Integer pageNum,
                                          @RequestParam(defaultValue = "4") Integer pageSize
    )
            //"诗词创作，诗词赏析，诗词学习，诗词活动，诗词资源，诗词杂谈"
    {   String type;
           if(type1==1){
               type="诗词创作";
           } else if(type1==2){
               type="诗词赏析";
           }else if(type1==3){
               type="诗词学习";
           }else if(type1==4){
               type="诗词活动";
           }else if(type1==5){
               type="诗词资源";
           }else if(type1==6){
               type="诗词杂谈";
           }else{
               throw new RuntimeException("参数错误");
           }
        PageResult pageInfo = poemLunTanService.GetPoemPage(pageNum, pageSize,type);

        return Result.success(pageInfo);
    }
    @ApiOperation(value="查询帖子详细")
    @GetMapping("selectxiangxi")
    private Result<PoemBlogVo> selectxiangxi(@RequestParam Integer blogid){
             return Result.success(poemLunTanService.selectxiangxi(blogid));
    }
    @ApiOperation(value="帖子点赞")
    @GetMapping("dianzan")
    private Result<String> dianzan(@RequestParam Integer blogid){
       boolean is= poemLunTanService.dianzan(blogid);
       if(is){
           return Result.success("点赞成功");
       }else{
           return Result.success("点赞取消");
       }

    }
    @ApiOperation(value="获取前5个点赞的")
    @GetMapping("dianzanrank")
    private Result<List<UserDianZanVo>> dianzanrank(@RequestParam Integer blogid){
        List<UserDianZanVo> dianzanrank = poemLunTanService.dianzanrank(blogid);
          if(dianzanrank==null){
              return Result.error("无点赞用户");
          }
        return Result.success(dianzanrank);
    }
    @ApiOperation(value="好友关注,先判断用户有没有关注")
    @GetMapping("isguanzhu")
    private Result<String> followor(@RequestParam Integer followUserid)
    {
        boolean flag =poemLunTanService.isfrend(followUserid);
          if(flag){
              return Result.success("已关注");
          }else{
              return Result.success("未关注");
          }
    }
    @ApiOperation(value="好友关注")
    @GetMapping("guanzhu")
     private Result guanzhu(@RequestParam Integer followUserid, @RequestParam boolean isFollow)
    {

        return  poemLunTanService.guanzhu(followUserid,isFollow);
    }
    @ApiOperation(value="查看别人的主页")
    @GetMapping("select/user/{followid}")
    private Result<BlogUserVo> selectuser(@PathVariable Integer followid){
        return Result.success(poemLunTanService.getByUsername(followid));
    }
    @ApiOperation(value="查看一个人发布的全部笔记")
    @GetMapping("select/blog/{followid}")
    private Result<PageResult> selectblog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "4") Integer pageSize,
            @PathVariable Integer followid
    ){
        PageResult pageInfo = poemLunTanService.selecttiezi(pageNum, pageSize,followid);
        return Result.success(pageInfo);

    }
    @ApiOperation(value="查看用户关注博主的发布的笔记")
    @GetMapping("select/guanzhu")
 public  Result selectguan(
         @RequestParam Long lasttimemax,
         @RequestParam(defaultValue = "0") Long offset){
      return  poemLunTanService.selectguanzhu(lasttimemax,offset);

    }

    @ApiOperation(value="发布评论")
    @PostMapping("fabacomment")
    private Result fabacomment(@RequestBody FourmCommentDto fourmCommentDto){
        Integer id= BaseContext.getCurrentId().intValue();
       return  poemLunTanService.fabucomment(fourmCommentDto,id);
    }

    @ApiOperation(value = "查询评论")
    @GetMapping("selectConmmets")
//List<FabaCommnetVo>
//PageResult
    private Result<List<FabaCommnetVo>>selectConmmets(@RequestParam Integer blogid

){
        return Result.success(poemLunTanService.selectConmmets(blogid));
}

@ApiOperation(value = "查询评论11")
    @GetMapping("selectConmmets11")
//List<FabaCommnetVo>
//PageResult
    private Result<PageResult>selectConmmets11(@RequestParam Integer blogid
,@RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize

){
        PageResult pageinfo=poemLunTanService.selectConmmets1(blogid,pageNum,pageSize);
        return Result.success(pageinfo);
}
@ApiOperation(value = "评论点赞")
    @GetMapping("commentdianzan")
    private Result<String> commentdianzan(@RequestParam Integer commentid){
       boolean is= poemLunTanService.commentdianzan(commentid);
       if(is){
           return Result.success("点赞成功");
       }else{
           return Result.success("点赞取消");
       }
    }
    @ApiOperation(value = "随机返回5个论坛")
    @GetMapping("select/forum")
    private Result<List<BlogVO>> selectforum(){
        return Result.success(poemLunTanService.selectforum1());
    }
    //内容 标题 id
    @ApiOperation(value="根据用户上传的内容来搜索古诗")
    @GetMapping("search")
    private Result<List<PoemSerchVo>> search(@RequestParam String content){
        List<PoemSerchVo> poemVos=poemLunTanService.search(content);
        return Result.success(poemVos);
    }

}
