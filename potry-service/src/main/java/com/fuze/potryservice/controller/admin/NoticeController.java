package com.fuze.potryservice.controller.admin;

import com.fuze.dto.NoticeDto;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.NoticeService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/notice")
@Slf4j
@Api(tags = "公告管理相关接口")
public class NoticeController {
    @Autowired
    private NoticeService NoticeService;
    @Autowired
    private NoticeService noticeService;

    @ApiOperation("添加公告")
    @AutoLog("添加公告")
    @PostMapping("/add")
    public Result addNotice(@RequestBody NoticeDto noticeDto) {
        log.info("添加公告:{}", noticeDto);
        NoticeService.add(noticeDto);
        return Result.success("添加成功");
    }
    @ApiOperation("批量删除公告")
    @AutoLog("删除公告")
    @PostMapping("/delete")
    public Result deleteNotice(@RequestParam List<Long> ids) {
        log.info("删除公告:{}", ids);
        NoticeService.delete(ids);
        return Result.success("删除成功");
    }
    @ApiOperation("获取公告列表(一次获取十条)")
    @GetMapping("/getList")
    public Result<PageResult> GetPage(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize
    ) {
        PageResult pageInfo = noticeService.GetPage(pageNum, pageSize);
        return Result.success(pageInfo);
    }
    @ApiOperation("更改公告")
    @AutoLog("更改公告")
    @PostMapping("/update")
    public Result updateNotice(@RequestBody NoticeDto noticeDto) {
        log.info("修改公告:{}", noticeDto);
        NoticeService.update(noticeDto);
        return Result.success("修改成功");
    }
@ApiOperation("获取公告（所有公告）")
@GetMapping("/get")
    public Result<List<NoticeDto>> getNotice() {
        List<NoticeDto> noticeDtoList = noticeService.getNotice();
        return Result.success(noticeDtoList);
    }
    //TODO暂时脑袋有点昏 通知之后再考虑


}
