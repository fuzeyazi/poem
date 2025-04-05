package com.fuze.potryservice.controller.admin;

import com.fuze.dto.CommentDto;
import com.fuze.dto.CommentFindDto;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.CommentService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageInfo;
import groovy.util.logging.Slf4j;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.websocket.server.PathParam;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController("adminCommentController")
@RequestMapping("/admin/comment")
@Api(tags = "论坛管理相关接口")
@Slf4j
public class CommentController {
    /*
    分页展示帖子
     */
    @Autowired
    private CommentService commentService;
    @ApiOperation("分页展示所有帖子")
    @GetMapping("/getcomment")
    public Result<PageResult> getCommentList(@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "20") Integer pageSize) {
        PageInfo<CommentVo> pageInfo = commentService.getCommentList(pageNum, pageSize);
        return Result.success(new PageResult(pageInfo.getTotal(), pageInfo.getList()));
    }
    @ApiOperation("展示帖子的详细信息")
    @GetMapping("/getcommentxaingxi/{id}")
    public Result<CommentVo>  getcommentxaingxi(@PathVariable Integer id){
        CommentVo commentVo = commentService.getCommentDetails((Integer) id);
        if (commentVo == null) {
            return Result.error("帖子不存在");
        }
        return Result.success(commentVo);
    }
    /*
    根据标题、作者、时间筛选帖子
    //TODO 不知道哪个是标题字段
     */
    @ApiOperation("根据作者、时间筛选帖子")
    @GetMapping("/getcommentBy")
    public Result<List<CommentVo>> getCommentListBy(@RequestBody CommentFindDto commentFinDto) {
       List<CommentVo> commentVos = commentService.getCommentListBy(commentFinDto);
       return Result.success(commentVos);
    }
//删除帖子
// TODo由于还是没理清帖子和评论的区别 将删除评论和帖子暂时为同一个接口
    @ApiOperation("根据id批量删除帖子/评论")
    @AutoLog("删除帖子/评论")
    @DeleteMapping("/delete")
    public Result deleteComment(@RequestParam List<Long> ids) {
        commentService.deleteComment(ids);
        return Result.success("删除成功");
    }

}