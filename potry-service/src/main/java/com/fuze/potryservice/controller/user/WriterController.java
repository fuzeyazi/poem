package com.fuze.potryservice.controller.user;

import com.fuze.vo.WriterVo;
import com.fuze.potryservice.service.WriterService;
import com.fuze.result.Result;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.WriterWithPoemsVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/user/writer")
@Api(tags = "用户对诗人的相关操作")
@Slf4j

public class WriterController {

    @Autowired
    private WriterService writerService;

    @ApiOperation(value = "获取诗人的总数")
    @GetMapping("/GetWriterCount")
    public Result<Integer> getWriterCount() {
        log.info("获取诗人总数：");
        Integer count = writerService.getWriterCount();
        return Result.success(count);
    }

    @ApiOperation(value = "获取所有诗人名称")
    @GetMapping("/GetAllWriterNames")
    public Result<List<String>> getAllWriterNames() {
        log.info("获取所有诗人名称：");
        List<String> list = writerService.getAllWriterNames();
        return Result.success(list);
    }

    @ApiOperation(value = "根据诗人名字查询图片和简要介绍")
    @GetMapping("/imageAndSimpleIntro")
    public Result<WriterVo> getImageAndSimpleIntro(@RequestParam String name) {
        WriterVo writer = writerService.getImageAndSimpleIntroByName(name);
        return Result.success(writer);
    }

    @ApiOperation(value = "根据诗人名字查询详细介绍")
    @GetMapping("/detailIntro")
    public Result<String> getDetailIntro(@RequestParam String name) {
        String detailIntro = writerService.getDetailIntroByName(name);
        return Result.success(detailIntro);
    }

    @ApiOperation(value = "查询不同朝代里有多少诗人")
    @GetMapping("/GetWritersByDynasty")
    public Result<List<String>> getWritersByDynasty(@RequestParam String dynasty) {
        log.info("查询朝代{}的诗人：", dynasty);
        List<String> writers = writerService.getWritersByDynasty(dynasty);
        return Result.success(writers);
    }

    @ApiOperation(value = "获取某个诗人的所有古诗")
    @GetMapping("/GetPoemsByWriter")
    public Result<List<PoemDataVo>> getPoemsByWriter(@RequestParam String writer) {
        log.info("获取诗人{}的所有古诗：", writer);
        List<PoemDataVo> poems = writerService.getPoemsByWriter(writer);
        return Result.success(poems);
    }

    @ApiOperation(value = "随机返回十个诗人")
    @GetMapping("/GetRandomPoems")
    public Result<List<PoemDataVo>> getRandomPoems() {
        log.info("随机返回十首古诗：");
        List<PoemDataVo> poems = writerService.getRandomPoems();
        return Result.success(poems);
    }

    @ApiOperation(value = "通过id查询作者及其相关联的所有作品")
    @GetMapping("/GetWriterAndPoemsById")
    public Result<WriterWithPoemsVo> getWriterAndPoemsById(@RequestParam Long id) {
        log.info("查询作者ID为{}的作者及其相关联的作品", id);
        WriterWithPoemsVo writerWithPoems = writerService.getWriterAndPoemsById(id);
        return Result.success(writerWithPoems);
    }

    @ApiOperation(value = "获取所有作者的所处朝代")
    @GetMapping("/GetAllDynasties")
    public Result<List<String>> getAllDynasties() {
        log.info("获取所有作者的所处朝代");
        List<String> dynasties = writerService.getAllDynasties();
        return Result.success(dynasties);
    }

    @ApiOperation(value = "通过id查询作者及其对应的一首诗")
    @GetMapping("/GetFamousLinesByWriterId")
    public Result<PoemDataVo> getFamousLinesByWriterId(@RequestParam Long id) {
        log.info("查询作者ID为{}的一首诗", id);
        PoemDataVo famousLines = writerService.getFamousLinesByWriterId(id);
//        List<String> famousLines = writerService.getFamousLinesByWriterId(id);
        return Result.success(famousLines);
    }

    @ApiOperation(value = "分页获取作者信息")
    @GetMapping("/GetWritersByPage")
    public Result<PageInfo<WriterVo>> getWritersByPage(@RequestParam(defaultValue = "1") int pageNum, @RequestParam(defaultValue = "15") int pageSize) {
        log.info("分页获取作者信息：pageNum={}, pageSize={}", pageNum, pageSize);
        PageInfo<WriterVo> pageInfo = writerService.getWritersByPage(pageNum, pageSize);
        return Result.success(pageInfo);
    }

    @ApiOperation(value = "随机获取5个诗人的具体信息")
    @GetMapping("/GetRandomWriters")
    public Result<List<WriterVo>> getRandomWriters() {
        log.info("随机获取5个诗人的信息");
        List<WriterVo> writers = writerService.getRandomWriters();
        return Result.success(writers);
    }
}
