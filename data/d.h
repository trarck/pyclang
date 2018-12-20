#pragma once

@interface UnityAppController
{
    NSInteger _myi;
    float _myf;
}
- (void)preStartUnity:(NSInteger) x aa:(float) y bb:(NSString*) str;
// override it to add your render plugin delegate
- (void)shouldAttachRenderDelegate;

// this one is called at the very end of didFinishLaunchingWithOptions:
// after views have been created but before initing engine itself
// override it to register plugins, tweak UI etc

@property (nonatomic, retain) id                            renderDelegate;
@property (nonatomic, copy)                                 void(^quitHandler)();

@end

