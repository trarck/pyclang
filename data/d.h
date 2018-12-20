#pragma once

@interface UnityAppController : NSObject
{
    NSInteger _myi;
    MSFloat _myf;
}

// override it to add your render plugin delegate
- (void)shouldAttachRenderDelegate;

// this one is called at the very end of didFinishLaunchingWithOptions:
// after views have been created but before initing engine itself
// override it to register plugins, tweak UI etc
- (void)preStartUnity;

@property (nonatomic, retain) id                            renderDelegate;
@property (nonatomic, copy)                                 void(^quitHandler)();

@end

