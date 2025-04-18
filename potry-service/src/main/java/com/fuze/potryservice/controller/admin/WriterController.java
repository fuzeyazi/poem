package com.fuze.potryservice.controller.admin;

import ch.qos.logback.core.recovery.ResilientFileOutputStream;
import com.fuze.dto.WriterDto;
import com.fuze.entity.Writer;
import com.fuze.potryservice.service.WriterService;
import com.fuze.result.Result;
import com.fuze.utils.AliOssUtil;
import com.fuze.vo.WriterVo;
import com.github.pagehelper.PageInfo;
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

@RestController("诗人管理端")
@Slf4j
@RequestMapping("/admin/writer")
@Api(tags = "诗人管理端")
public class WriterController {
    @Autowired
    private WriterService writerService;
    @Autowired
    private AliOssUtil aliOssUtil;
    @ApiOperation(value = "分页获取诗人信息")
    @GetMapping("/GetWritersByPage")
    public Result<PageInfo<WriterVo>> getWritersByPage(@RequestParam(defaultValue = "1") int pageNum, @RequestParam(defaultValue = "15") int pageSize) {
        log.info("分页获取作者信息：pageNum={}, pageSize={}", pageNum, pageSize);
        PageInfo<WriterVo> pageInfo = writerService.getWritersByPage(pageNum, pageSize);
        return Result.success(pageInfo);
    }
    @ApiOperation(value = "上传图片")
    @PostMapping("/updateImage")
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
@ApiOperation("新增诗人")
@PostMapping("/add")
 public Result add(@RequestBody WriterDto writerDto)
{
    log.info("新增诗人");
    writerService.add(writerDto);
    return Result.success("新增诗人成功");
}
@ApiOperation("批量删除诗人")
    @PostMapping("/delete")
    public Result delete(@RequestParam List<Long> ids)
    {
        log.info("批量删除诗人");
        writerService.delete(ids);
        return Result.success("批量删除诗人成功");
    }
    @ApiOperation("修改诗人信息")
    @PostMapping("/update")
    public Result update(@RequestBody WriterDto writerDto)
    {
        log.info("修改诗人信息");
        writerService.save(writerDto);
        return Result.success("修改诗人信息成功");
    }
    @ApiOperation("根据id获取诗人信息")
    @GetMapping("/{id}")
    public Result<WriterVo> getWriterById(@PathVariable int id)
    {
        log.info("根据获取诗人信息");
        WriterVo writerVo=writerService.getWriterById(id);
        return Result.success(writerVo);
    }
    @ApiOperation("根据名称查询诗人模糊查询")
    @GetMapping("/getWriterByName")
    public Result<List<WriterVo>> getWriterByName(@RequestParam String name)
    {
        log.info("根据名称查询诗人:{}",name);
        List<WriterVo> writerVo=writerService.getWriterByName(name);
        return Result.success(writerVo);
    }
    @ApiOperation("获取诗人数量")
    @GetMapping("/getCount")
    public Result<Integer> getCount()
    {
        log.info("获取诗人数量");
        Integer count=writerService.getWriterCount();
        return Result.success(count);
    }
}
