package com.fuze.potryservice.controller.admin;

import com.fuze.dto.CommentDto;
import com.fuze.dto.CommentFindDto;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
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
@RequestMapping("/admin/blog")
@Api(tags = "帖子管理相关接口")
@Slf4j
public class CommentController {
    @Autowired
    private com.fuze.potryservice.mapper.PoemLunTanMapper poemLunTanMapper;
 @Autowired
    private AdminService adminService;
 @ApiOperation("分页获取所有帖子")
    @GetMapping("/getAllBlog")
 public Result<PageResult> GetAllBlog(
         @RequestParam(defaultValue = "1") Integer pageNum,
         @RequestParam(defaultValue = "10") Integer pageSize
 ) {
     PageResult pageInfo = adminService.GetBlog(pageNum, pageSize);
     return Result.success(pageInfo);
 }
@ApiOperation("批量删除帖子")
    /** 按帖查评论(管理端,含压测数据清理场景) */
    @GetMapping("/comments")
    public Result<PageResult> comments(@RequestParam Integer blogid,
                                       @RequestParam(defaultValue = "1") Integer pageNum,
                                       @RequestParam(defaultValue = "20") Integer pageSize) {
        com.github.pagehelper.PageHelper.startPage(pageNum, pageSize);
        com.github.pagehelper.Page<com.fuze.vo.FabaCommnetVo> page = poemLunTanMapper.selectConmme1t11(blogid);
        return Result.success(new PageResult(page.getTotal(), page.getResult()));
    }

    /** 删除评论(支持批量;不联动帖子评论计数,管理清理场景可接受) */
    @PostMapping("/deleteComment")
    public Result deleteComment(@RequestParam List<Integer> ids) {
        poemLunTanMapper.deleteComments(ids);
        return Result.success("删除成功");
    }

    @PostMapping("/deleteBlog")
    public Result deleteBlog(@RequestParam List<Integer> ids) {
        adminService.deleteBlogById(ids);
        return Result.success();
    }

}