package com.fuze.potryservice.controller.admin;

import com.fuze.dto.ReplyDto;
import com.fuze.entity.FeedBack;
import com.fuze.potryservice.service.FeedBackService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.FeedBackVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/feedback")
@Api(tags = "管理端用户反馈处理接口")
@Slf4j
public class AdminFeedBackController {

    @Autowired
    private FeedBackService feedBackService;

    @ApiOperation(value = "管理员查看所有用户的反馈")
    @GetMapping("/getAllFeedBack")
    public Result<List<FeedBack>> getAllFeedBack() {
        return Result.success(feedBackService.getAllFeedBack());
    }

    @ApiOperation("通过反馈id查询留言详情")
    @GetMapping("/{id}")
    public Result<FeedBack> getFeedBack(@PathVariable Integer id) {
        return Result.success(feedBackService.getFeedBack(id));
    }

    @ApiOperation("分页查询用户留言反馈")
    @GetMapping("/page")
    public Result<PageResult> selectPageFeedBackVO(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "15") Integer pageSize) {
        PageInfo<FeedBackVo> feedBackVOPageInfo = feedBackService.selectPage(pageNum, pageSize);
        PageResult pageResult = new PageResult(feedBackVOPageInfo.getTotal(), feedBackVOPageInfo.getList());
        return Result.success(pageResult);
    }

    @ApiOperation("兼容原有路径的分页查询用户留言反馈")
    @GetMapping("/Getpage")
    public Result<PageResult> legacyGetPage(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "15") Integer pageSize) {
        return selectPageFeedBackVO(pageNum, pageSize);
    }

    @ApiOperation("通过id删除用户留言")
    @DeleteMapping("/{id}")
    public Result<String> deleteFeedback(@PathVariable Integer id) {
        feedBackService.deletefeedback(id);
        return Result.success("删除成功");
    }

    @ApiOperation("兼容原有路径删除用户留言")
    @DeleteMapping("/deletefeedback/{id}")
    public Result<String> legacyDeleteFeedback(@PathVariable Integer id) {
        return deleteFeedback(id);
    }

    @ApiOperation("管理员回复用户留言")
    @PutMapping("/reply")
    public Result<String> replyFeedback(@RequestBody ReplyDto replyDto) {
        feedBackService.addreply(replyDto);
        return Result.success("回复成功");
    }

    @ApiOperation("兼容原有路径管理员回复用户留言")
    @PutMapping("/updatefeedback")
    public Result<String> legacyUpdateFeedback(@RequestBody ReplyDto replyDto) {
        return replyFeedback(replyDto);
    }
}
